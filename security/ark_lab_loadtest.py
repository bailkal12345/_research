# -*- coding: utf-8 -*-
"""
ark_lab_loadtest.py — лабораторный стенд нагрузки на ARK SE (без RCON).

Стенд измеряет, как сервер ARK реагирует на узкоспециализированные паттерны
трафика на штатных портах, и даёт измерения для проектирования защиты.

Метрики берутся с серверного плагина NetGuard по TCP 127.0.0.1:27101
(TPS, tickMs, живые соединения, попытки соединения, пакеты) - RCON для
измерений не используется.

Сценарии (подкоманды):
  query        одиночный A2S/Steam-query и разбор ответа
  query-flood  поток A2S на query-порт (измеряем отклик и нагрузку)
  game-flood   UDP-флуд на игровой порт (с измерением просадки FPS)
  suite        прогон всех сценариев со сводной таблицей

Ограничения: только 127.0.0.1 / 192.168.8.218 (локальный стенд), никакого
спуфинга, никаких внешних целей, ограничение по объёму и времени.

Примеры:
  python ark_lab_loadtest.py query --host 192.168.8.218 --query-port 27016
  python ark_lab_loadtest.py query-flood --host 192.168.8.218 --query-port 27016 --pps 2000 --duration 15
  python ark_lab_loadtest.py game-flood --host 192.168.8.218 --game-port 7778 --pps 5000 --duration 15
  python ark_lab_loadtest.py suite
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
from ark_lab_net import (  # noqa: E402
    A2SError,
    LabTargetError,
    ProcessMeter,
    a2s_challenge,
    a2s_info,
    a2s_player,
    a2s_player_rules,
    guard_target,
    make_query_socket,
    pick_pid,
)

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

MB = 1024.0 * 1024.0


# ---------------------------------------------------------------------------
# Печать
# ---------------------------------------------------------------------------

def hr(title: str = "") -> None:
    if title:
        print("\n" + "=" * 78)
        print(title)
        print("=" * 78)
    else:
        print("-" * 78)


def fmt_ms(v: float | None) -> str:
    return "n/a" if v is None else "%8.1f" % v


class Pacer:
    """Планировщик темпа: каждый поток забирает свой слот по дедлайну."""

    def __init__(self, total_pps: int, nthreads: int):
        self.interval = nthreads / max(1.0, float(total_pps))
        self._lock = threading.Lock()
        self._next = time.perf_counter()

    def wait(self) -> None:
        with self._lock:
            slot = self._next
            self._next += self.interval
        now = time.perf_counter()
        if slot > now:
            time.sleep(slot - now)
        elif now - slot > 1.0:
            with self._lock:
                self._next = now + self.interval


# ---------------------------------------------------------------------------
# Метрики через NetGuard (RCON не используется)
# ---------------------------------------------------------------------------

class Probe:
    """Метрики сервера: TPS/tickMs из плагина NetGuard + CPU процесса."""

    def __init__(self, args):
        self.args = args
        self.pid = pick_pid("ShooterGameServer.exe", args.server_filter)
        self.meter = ProcessMeter(self.pid)
        self._client = None
        if self.pid is None:
            print("[!] ShooterGameServer.exe не найден - метрики CPU недоступны,")
            print("    но метрики плагина NetGuard работают.")

    def client(self) -> NetGuardClient | None:
        if self._client is None:
            try:
                self._client = NetGuardClient(self.args.metrics_host,
                                              self.args.metrics_port).connect()
            except (OSError, MetricsError) as exc:
                print("[!] NetGuard недоступен (%r) - метрики TPS недоступны" % (exc,))
                return None
        return self._client

    def status(self) -> dict:
        c = self.client()
        if c is None:
            return {}
        try:
            return c.status()
        except (OSError, MetricsError):
            self._client = None
            return {}

    def close(self) -> None:
        if self._client:
            self._client.close()
            self._client = None


def snapshot(probe: Probe, label: str) -> dict:
    """Снимок: tps/tickMs (плагин) + CPU процесса."""
    s = probe.status()
    m = probe.meter.sample()
    return {
        "label": label,
        "t": time.time(),
        "cpu": m["cpu"],
        "ws_mb": m["ws"] / MB,
        "tps": float(s.get("tps", 0.0) or 0.0),
        "tickMs": float(s.get("tickMs", 0.0) or 0.0),
        "live": int(s.get("liveConnections", 0) or 0),
        "attempts": int(s.get("connectionAttempts", 0) or 0),
        "packets": int(s.get("packetsReceived", 0) or 0),
    }


def cpu_pct_between(a: dict, b: dict) -> float:
    dt = b["t"] - a["t"]
    if dt <= 0:
        return 0.0
    return max(0.0, (b["cpu"] - a["cpu"]) / dt * 100.0)


# ---------------------------------------------------------------------------
# Сценарий: одиночный A2S-запрос
# ---------------------------------------------------------------------------

def sc_query(args) -> dict:
    hr("Сценарий query: одиночный A2S/Steam-query на %s:%d" % (args.host, args.query_port))
    addr = (args.host, args.query_port)
    result = {}
    sock = make_query_socket(timeout=3.0)
    try:
        challenge = a2s_challenge(sock, addr)
        print("  challenge: %s" % (challenge.hex() if challenge else "(сервер сразу ответил A2S_INFO)"))
        info = a2s_info(sock, addr, challenge, optional=True)
        if info is None:
            print("  A2S_INFO: сервер не отвечает на 0x49 (так устроена Steam-серверная API ARK)")
        else:
            print("  A2S_INFO (%d байт):" % info["raw_len"])
            for k in ("name", "map", "folder", "game", "appid", "players", "maxplayers", "keywords"):
                if info.get(k):
                    print("      %-11s = %s" % (k, info[k]))
            result["info"] = info
        if challenge:
            rules = a2s_player_rules(sock, addr, challenge)
            print("  A2S_PLAYER_RULES (%d правил, ответ 0x45):" % len(rules))
            for k, v in rules.items():
                print("      %-20s = %s" % (k, v))
            result["rules"] = rules
            try:
                players = a2s_player(sock, addr, challenge)
                print("  A2S_PLAYER: %s" % (", ".join(players) if players else "(пусто)"))
                result["players"] = players
            except (A2SError, OSError) as exc:
                print("  A2S_PLAYER: %r" % (exc,))
    except (A2SError, OSError) as exc:
        print("  ОШИБКА: %r" % (exc,))
        result["error"] = repr(exc)
    finally:
        sock.close()
    return result


# ---------------------------------------------------------------------------
# Сценарий: флуд A2S
# ---------------------------------------------------------------------------

def sc_query_flood(args, probe: Probe) -> dict:
    hr("Сценарий query-flood: %d пакетов/с на %s:%d в течение %d с"
       % (args.pps, args.host, args.query_port, args.duration))
    addr = (args.host, args.query_port)
    stop = threading.Event()
    sent = [0]
    replies = [0]
    latencies: list[float] = []
    lock = threading.Lock()
    pacer = Pacer(args.pps, max(1, args.threads))

    def worker() -> None:
        s = make_query_socket(timeout=1.0)
        try:
            while not stop.is_set():
                pacer.wait()
                t0 = time.perf_counter()
                try:
                    s.sendto(b"\xff\xff\xff\xff\x54Source Engine Query\x00", addr)
                    with lock:
                        sent[0] += 1
                    s.recv(4096)
                    with lock:
                        replies[0] += 1
                        latencies.append((time.perf_counter() - t0) * 1000.0)
                except (socket.timeout, OSError):
                    pass
        finally:
            s.close()

    threads = []
    for _ in range(max(1, args.threads)):
        t = threading.Thread(target=worker, daemon=True)
        t.start()
        threads.append(t)

    base = snapshot(probe, "baseline")
    t_start = time.time()
    while time.time() - t_start < args.duration:
        time.sleep(1.0)
        now = snapshot(probe, "during")
        el = time.time() - t_start
        print("  t+%3ds  CPU %5.1f%%  tps %5.1f  tick %6.2f ms  пакетов %d (%.0f pps)  ответов %d"
              % (el, cpu_pct_between(base, now), now["tps"], now["tickMs"],
                 sent[0], sent[0] / max(1.0, el), replies[0]))
    stop.set()
    for t in threads:
        t.join(timeout=2.0)
    during = snapshot(probe, "during-final")
    time.sleep(3.0)
    after = snapshot(probe, "recovery")
    el = max(1.0, time.time() - t_start)
    print("\n  ИТОГО: отправлено %d (%.0f pps), ответов %d (%.1f%%)"
          % (sent[0], sent[0] / el, replies[0], 100.0 * replies[0] / max(1, sent[0])))
    print("  CPU за окно: %.1f%%   tps: %.1f -> %.1f   tick: %.2f -> %.2f ms"
          % (cpu_pct_between(base, during), base["tps"], during["tps"],
             base["tickMs"], during["tickMs"]))
    if latencies:
        srt = sorted(latencies)
        print("  RTT: медиана %.1f ms, p95 %.1f ms, max %.1f ms"
              % (statistics.median(srt), srt[int(len(srt) * 0.95) - 1], srt[-1]))
    return {"sent": sent[0], "replies": replies[0], "pps": sent[0] / el,
            "cpu_pct": cpu_pct_between(base, during),
            "tps_base": base["tps"], "tps_after": during["tps"]}


# ---------------------------------------------------------------------------
# Сценарий: флуд игрового порта
# ---------------------------------------------------------------------------

def sc_game_flood(args, probe: Probe) -> dict:
    hr("Сценарий game-flood: %d пакетов/с на игровой порт %s:%d в течение %d с"
       % (args.pps, args.host, args.game_port, args.duration))
    addr = (args.host, args.game_port)
    stop = threading.Event()
    sent = [0]
    lock = threading.Lock()
    pacer = Pacer(args.pps, max(1, args.threads))

    def worker() -> None:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            payload = os.urandom(args.payload_size)
            while not stop.is_set():
                pacer.wait()
                try:
                    # каждый пакет - с нового порта источника
                    x = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    try:
                        x.sendto(payload, addr)
                    finally:
                        x.close()
                    with lock:
                        sent[0] += 1
                except OSError:
                    pass
        finally:
            s.close()

    threads = []
    for _ in range(max(1, args.threads)):
        t = threading.Thread(target=worker, daemon=True)
        t.start()
        threads.append(t)

    base = snapshot(probe, "baseline")
    t_start = time.time()
    while time.time() - t_start < args.duration:
        time.sleep(1.0)
        now = snapshot(probe, "during")
        el = time.time() - t_start
        print("  t+%3ds  CPU %5.1f%%  tps %5.1f  tick %6.2f ms  соединений %d  пакетов %d (%.0f pps)"
              % (el, cpu_pct_between(base, now), now["tps"], now["tickMs"],
                 now["live"], sent[0], sent[0] / max(1.0, el)))
    stop.set()
    for t in threads:
        t.join(timeout=2.0)
    during = snapshot(probe, "during-final")
    time.sleep(3.0)
    after = snapshot(probe, "recovery")
    el = max(1.0, time.time() - t_start)
    print("\n  ИТОГО: пакетов %d (%.0f pps), CPU за окно %.1f%%"
          % (sent[0], sent[0] / el, cpu_pct_between(base, during)))
    print("  tps: %.1f -> %.1f   tick: %.2f -> %.2f ms   живых соединений %d -> %d"
          % (base["tps"], during["tps"], base["tickMs"], during["tickMs"],
             base["live"], during["live"]))
    return {"sent": sent[0], "pps": sent[0] / el, "cpu_pct": cpu_pct_between(base, during),
            "tps_base": base["tps"], "tps_after": during["tps"],
            "tick_base": base["tickMs"], "tick_after": during["tickMs"]}


# ---------------------------------------------------------------------------
# Сводка
# ---------------------------------------------------------------------------

def print_summary(results: dict) -> None:
    hr("СВОДКА")
    print("%-14s %10s %12s %12s %14s" % ("сценарий", "пакетов", "CPU %", "tps фон", "tps после"))
    print("-" * 78)
    for label, key in (("query-flood", "query-flood"), ("game-flood", "game-flood")):
        r = results.get(key)
        if not r:
            continue
        print("%-14s %10d %12.1f %12.1f %14.1f"
              % (label, r.get("sent", 0), r.get("cpu_pct", 0.0),
                 r.get("tps_base", 0.0), r.get("tps_after", 0.0)))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Лабораторный стенд нагрузки на ARK SE (только localhost/стенд)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("scenario", choices=["query", "query-flood", "game-flood", "suite"])
    p.add_argument("--host", default="192.168.8.218", help="адрес стенда")
    p.add_argument("--query-port", type=int, default=27016, help="порт Steam-query")
    p.add_argument("--game-port", type=int, default=7778, help="игровой порт")
    p.add_argument("--metrics-host", default="127.0.0.1", help="хост плагина NetGuard")
    p.add_argument("--metrics-port", type=int, default=27101, help="порт плагина NetGuard")
    p.add_argument("--server-filter", default="Server2",
                   help="подстрока пути к exe сервера для метрик CPU")
    p.add_argument("--pps", type=int, default=1000, help="пакетов в секунду")
    p.add_argument("--duration", type=int, default=15, help="длительность флуда, с")
    p.add_argument("--threads", type=int, default=8, help="число потоков-отправителей")
    p.add_argument("--payload-size", type=int, default=64)
    p.add_argument("--allow-any", action="store_true",
                   help="разрешить не-стендовые адреса (в лаборатории НЕ использовать)")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        guard_target(args.host, args.allow_any)
    except LabTargetError as exc:
        print("[!] %s" % (exc,))
        return 2

    hr("ARK SE — лабораторный стенд нагрузки")
    print("  цель            : %s" % args.host)
    print("  query-port      : %d" % args.query_port)
    print("  game-port       : %d" % args.game_port)
    print("  метрики         : %s:%d (плагин NetGuard)" % (args.metrics_host, args.metrics_port))
    print("  сценарий        : %s" % args.scenario)

    probe = Probe(args)
    results: dict = {}
    try:
        if args.scenario == "query":
            results["query"] = sc_query(args)
        elif args.scenario == "query-flood":
            results["query-flood"] = sc_query_flood(args, probe)
        elif args.scenario == "game-flood":
            results["game-flood"] = sc_game_flood(args, probe)
        elif args.scenario == "suite":
            results["query"] = sc_query(args)
            results["query-flood"] = sc_query_flood(args, probe)
            results["game-flood"] = sc_game_flood(args, probe)
    except KeyboardInterrupt:
        print("\n[!] прервано пользователем")
    finally:
        probe.close()
    if len(results) > 1:
        print_summary(results)
    return 0


if __name__ == "__main__":
    sys.exit(main())

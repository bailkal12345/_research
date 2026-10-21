# -*- coding: utf-8 -*-
"""
ark_lab_remote_probe.py — внешний зонд состояния удалённого сервера.

Плагин NetGuard стоит только на локальном стенде, поэтому состояние УДАЛЁННОГО
сервера измеряется косвенно - по времени ответа его query-порта (A2S).
Рост RTT = сервер перегружен (тик не успевает).

Запуск (мониторинг во время атаки):
    python ark_lab_remote_probe.py --host 23.109.45.13 --query-port 25715 --seconds 60
"""
from __future__ import annotations

import argparse
import socket
import statistics
import sys
import time

A2S_INFO = b"\xff\xff\xff\xffTSource Engine Query\x00"
A2S_PLAYER = b"\xff\xff\xff\xffU"


def a2s_rtt(host: str, port: int, timeout: float = 2.0) -> tuple[float | None, int]:
    """Один A2S-запрос: (RTT в мс, размер ответа) либо (None, 0) при таймауте."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    t0 = time.perf_counter()
    try:
        s.sendto(A2S_INFO, (host, port))
        data, _ = s.recvfrom(4096)
        return (time.perf_counter() - t0) * 1000.0, len(data)
    except (socket.timeout, OSError):
        return None, 0
    finally:
        s.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="Внешний зонд: RTT до query-порта удалённого сервера")
    ap.add_argument("--host", required=True)
    ap.add_argument("--query-port", type=int, default=27016)
    ap.add_argument("--seconds", type=float, default=60.0)
    ap.add_argument("--interval", type=float, default=0.5)
    ap.add_argument("--timeout", type=float, default=2.0)
    ap.add_argument("--json", default="", help="сохранить таймлайн в JSON")
    args = ap.parse_args()

    print("зонд: %s:%d, %.0f с" % (args.host, args.query_port, args.seconds))
    print("%8s %10s %10s %8s" % ("t, с", "RTT, мс", "медиана", "ответ, Б"))
    t0 = time.time()
    samples: list[tuple[float, float | None, int]] = []
    while time.time() - t0 < args.seconds:
        rtt, size = a2s_rtt(args.host, args.query_port, args.timeout)
        el = time.time() - t0
        samples.append((el, rtt, size))
        ok = [s[1] for s in samples if s[1] is not None]
        med = statistics.median(ok) if ok else float("nan")
        print("%8.1f %10s %10.1f %8d" % (el, ("%.1f" % rtt) if rtt is not None else "таймаут", med, size))
        time.sleep(args.interval)

    ok = [s[1] for s in samples if s[1] is not None]
    lost = len(samples) - len(ok)
    if ok:
        print("итого: успешных %d из %d, RTT мин %.1f / медиана %.1f / макс %.1f мс, потеряно %d" % (
            len(ok), len(samples), min(ok), statistics.median(ok), max(ok), lost))
    else:
        print("итого: ни одного успешного ответа, потеряно %d из %d" % (lost, len(samples)))
    if args.json:
        import json
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump([{"t": t, "rtt_ms": r, "bytes": b} for t, r, b in samples], f, indent=1)
        print("таймлайн сохранён: %s" % args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())

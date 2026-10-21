# -*- coding: utf-8 -*-
"""
ark_lab_remote_threshold.py — порог деградации на УДАЛЁННОМ сервере.

Локально порог обвала - ~80-100 тыс. поддельных GNS-пакетов (TPS 21.7 -> 2.5).
Вопрос: тот же порог на внешнем сервере или там он выше (больше CPU/ядр)?

Метод: ступенчато увеличиваем объём флуда, параллельно зондируя query-порт
(потери ответов + RTT) - это независимый от плагина сигнал.

Пример:
    python ark_lab_remote_threshold.py --host 23.109.45.13 --game-port 25714 \
        --query-port 25715 --steps 100000,200000,300000,500000
"""
from __future__ import annotations

import argparse
import os
import statistics
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ark_lab_gns_amp import run_amp  # noqa: E402
from ark_lab_remote_probe import a2s_rtt  # noqa: E402


class Probe(threading.Thread):
    def __init__(self, host: str, port: int, interval: float = 0.2):
        super().__init__(daemon=True)
        self.host, self.port, self.interval = host, port, interval
        self.samples: list[tuple[float, float | None]] = []
        self._stop = threading.Event()

    def run(self) -> None:
        t0 = time.time()
        while not self._stop.is_set():
            res = a2s_rtt(self.host, self.port, 1.5)
            self.samples.append((time.time() - t0, res[0] if isinstance(res, tuple) else res))
            self._stop.wait(self.interval)

    def stop(self) -> None:
        self._stop.set()

    def window(self, t0: float, t1: float) -> dict:
        sel = [r for t, r in self.samples if t0 <= t <= t1]
        ok = [r for r in sel if r is not None]
        return {"n": len(sel), "lost": len(sel) - len(ok),
                "lost_pct": round(100.0 * (len(sel) - len(ok)) / max(1, len(sel)), 1),
                "rtt_med": round(statistics.median(ok), 1) if ok else None,
                "rtt_max": round(max(ok), 1) if ok else None}


def main() -> int:
    ap = argparse.ArgumentParser(description="Порог деградации на удалённом сервере")
    ap.add_argument("--host", required=True)
    ap.add_argument("--game-port", type=int, required=True)
    ap.add_argument("--query-port", type=int, required=True)
    ap.add_argument("--steps", default="100000,200000,300000,500000")
    ap.add_argument("--variant", default="unreliable")
    ap.add_argument("--probe", type=float, default=12.0, help="окно зонда до флуда, с")
    ap.add_argument("--after", type=float, default=8.0, help="окно зонда после флуда, с")
    ap.add_argument("--cooldown", type=float, default=40.0)
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    steps = [int(x) for x in args.steps.split(",")]
    results = []
    for count in steps:
        pr = Probe(args.host, args.query_port)
        pr.start()
        time.sleep(args.probe)                      # базовое окно (без флуда)
        t_flood = time.time()
        r = run_amp(host=args.host, game_port=args.game_port,
                    metrics_host="127.0.0.1", metrics_port=27101,
                    count=count, duration=0.0, variant=args.variant,
                    use_metrics=False, verbose=False, check=False)
        t_end = time.time()
        time.sleep(args.after)
        pr.stop()
        during = pr.window(args.probe, t_end - t_flood + args.probe)
        base = pr.window(0.0, args.probe)
        results.append({"count": count, "pps": r["pps"], "during": during, "base": base,
                        "seconds": r["seconds"]})
        print("  %7d пакетов @ %6.0f pps (%.1f с): потери во время флуда %5.1f%% (база %4.1f%%), RTT медиана %s / макс %s" % (
            count, r["pps"], r["seconds"], during["lost_pct"], base["lost_pct"],
            during["rtt_med"], during["rtt_max"]))
        time.sleep(args.cooldown)

    print()
    print("=" * 100)
    print("ПОРОГ ДЕГРАДАЦИИ НА УДАЛЁННОМ СЕРВЕРЕ %s:%d (вариант %s)" % (args.host, args.game_port, args.variant))
    print("=" * 100)
    print("%10s %10s %9s %12s %12s %12s" % (
        "пакетов", "pps", "секунд", "потери(флуд)", "потери(база)", "RTT макс"))
    for r in results:
        print("%10d %10.0f %9.1f %11.1f%% %11.1f%% %12s" % (
            r["count"], r["pps"], r["seconds"], r["during"]["lost_pct"],
            r["base"]["lost_pct"], r["during"]["rtt_max"]))
    print("=" * 100)
    if args.json:
        import json
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print("сохранено: %s" % args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())

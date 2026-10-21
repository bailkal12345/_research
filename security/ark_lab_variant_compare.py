# -*- coding: utf-8 -*-
"""
ark_lab_variant_compare.py — сравнение вариантов data-пакета GNS по эффекту.

Для локального стенда основной сигнал - FPS/TPS плагина NetGuard.
Для удалённого стенда (плагина там нет) - косвенный сигнал: потери ответов
query-порта во время флуда и рост RTT (зонд работает в отдельном потоке).

Примеры:
    # локально: по FPS
    python ark_lab_variant_compare.py --count 150000 --seconds 12
    # удалённо: по потерям на query-порту
    python ark_lab_variant_compare.py --host 23.109.45.13 --game-port 25714 \
        --query-port 25715 --count 150000 --seconds 12 --remote
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
from ark_lab_metrics import NetGuardClient  # noqa: E402
from ark_lab_gns_amp import VARIANTS, run_amp  # noqa: E402
from ark_lab_remote_probe import a2s_rtt  # noqa: E402


class Probe(threading.Thread):
    """Фоновый зонд query-порта: считает потери и RTT."""

    def __init__(self, host: str, port: int, interval: float = 0.2):
        super().__init__(daemon=True)
        self.host, self.port, self.interval = host, port, interval
        self.samples: list[tuple[float, float | None]] = []
        self._stop = threading.Event()

    def run(self) -> None:
        t0 = time.time()
        while not self._stop.is_set():
            res = a2s_rtt(self.host, self.port, 1.5)
            rtt = res[0] if isinstance(res, tuple) else res
            self.samples.append((time.time() - t0, rtt))
            self._stop.wait(self.interval)

    def stop(self) -> None:
        self._stop.set()

    def window(self, t_from: float, t_to: float) -> dict:
        sel = [r for t, r in self.samples if t_from <= t <= t_to]
        ok = [r for r in sel if r is not None]
        return {"n": len(sel), "lost": len(sel) - len(ok),
                "lost_pct": round(100.0 * (len(sel) - len(ok)) / max(1, len(sel)), 1),
                "rtt_med": round(statistics.median(ok), 1) if ok else None,
                "rtt_max": round(max(ok), 1) if ok else None}


def main() -> int:
    ap = argparse.ArgumentParser(description="Сравнение вариантов data-пакета GNS")
    ap.add_argument("--host", default="192.168.8.218")
    ap.add_argument("--game-port", type=int, default=7778)
    ap.add_argument("--query-port", type=int, default=27016)
    ap.add_argument("--metrics-port", type=int, default=27101)
    ap.add_argument("--count", type=int, default=150000)
    ap.add_argument("--seconds", type=float, default=12.0)
    ap.add_argument("--cooldown", type=float, default=25.0)
    ap.add_argument("--remote", action="store_true",
                    help="цель удалённая (нет локального плагина) - мерить по потерям на query-порту")
    ap.add_argument("--only", action="append", choices=VARIANTS)
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    names = args.only or list(VARIANTS)
    m = NetGuardClient("127.0.0.1", args.metrics_port).connect()
    results = []
    for name in names:
        # восстановление сервера перед вариантом
        while True:
            tps = float(m.status().get("tps") or 0.0)
            if tps >= 19.0:
                break
            time.sleep(2.0)
        base_tps = tps
        pr = Probe(args.host, args.query_port)
        pr.start()
        time.sleep(1.0)
        t_start = time.time()
        r = run_amp(host=args.host, game_port=args.game_port,
                    metrics_host="127.0.0.1", metrics_port=args.metrics_port,
                    count=args.count, duration=args.seconds, variant=name,
                    use_metrics=not args.remote, metrics=m, verbose=False,
                    check=False)
        t_flood = time.time() - t_start
        time.sleep(1.0)
        pr.stop()
        during = pr.window(1.0, t_flood)
        after = m.status()
        r.update({"variant": name, "tps0": base_tps, "tps_min": r["tps_min"],
                  "tps_after": float(after.get("tps") or 0.0),
                  "conn_delta": r["conn_delta"], "remote_during": during})
        results.append(r)
        print("  %-14s пакетов=%-7d pps=%-7.0f  TPS %s->%s (мин %s)  потери на query: %s%%  RTT макс %s  соединений %+d" % (
            name, r["packets"], r["pps"], base_tps, r["tps_after"], r["tps_min"],
            during["lost_pct"], during["rtt_max"], r["conn_delta"]))
        time.sleep(args.cooldown)

    print()
    print("=" * 112)
    print("СРАВНЕНИЕ ВАРИАНТОВ DATA-ПАКЕТА GNS (цель: %s:%d)" % (args.host, args.game_port))
    print("=" * 112)
    print("%-14s %9s %8s %9s %9s %9s %12s %10s" % (
        "вариант", "пакетов", "pps", "TPS было", "TPS мин", "TPS после", "потери query", "соединений"))
    for r in results:
        print("%-14s %9d %8.0f %9s %9s %9s %11s%% %10d" % (
            r["variant"], r["packets"], r["pps"], r["tps0"], r["tps_min"], r["tps_after"],
            r["remote_during"]["lost_pct"], r["conn_delta"]))
    print("=" * 112)
    if args.json:
        import json
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print("сохранено: %s" % args.json)
    m.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

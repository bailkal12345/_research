# -*- coding: utf-8 -*-
"""
ark_lab_gns_why.py — почему падает FPS: CPU игрового треда или блокировка?

Снимает CPU процесса сервера (GetProcessTimes) и TPS плагина раз в 0.5 с
ПОКА идёт флуд. Если CPU в момент падения TPS остаётся низким, значит игровой
тред не вычисляет, а ждёт (блокировка/ожидание) - и это другой механизм.

Пример:
    python ark_lab_gns_why.py --count 150000
"""
from __future__ import annotations

import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ark_lab_metrics import NetGuardClient  # noqa: E402
from ark_lab_gns_amp import run_amp  # noqa: E402
from ark_lab_gns_cost import process_cpu_seconds  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="CPU сервера во время падения FPS")
    ap.add_argument("--host", default="192.168.8.218")
    ap.add_argument("--game-port", type=int, default=7778)
    ap.add_argument("--metrics-port", type=int, default=27101)
    ap.add_argument("--count", type=int, default=150000)
    ap.add_argument("--variant", default="unreliable")
    args = ap.parse_args()

    m = NetGuardClient("127.0.0.1", args.metrics_port).connect()
    pid = int(m.status().get("pid") or 0)
    print("сервер pid=%d" % pid)

    t0 = time.time()
    cpu0 = process_cpu_seconds(pid)
    r = run_amp(host=args.host, game_port=args.game_port, count=args.count, duration=0.0,
                variant=args.variant, use_metrics=True, metrics=m, verbose=False, check=False)
    t1 = time.time()
    cpu1 = process_cpu_seconds(pid)
    st = m.status()
    print("флуд: %d пакетов за %.1f с (%.0f pps)" % (r["packets"], t1 - t0, r["pps"]))
    print("CPU сервера за это время: %.2f с = %.0f%% одного ядра" % (
        cpu1 - cpu0, 100.0 * (cpu1 - cpu0) / max(1e-6, t1 - t0)))
    print("TPS: было %.1f, во время флуда мин %.1f, сейчас %.1f" % (
        r["tps0"], r["tps_min"], float(st.get("tps") or 0.0)))
    print("tickMs: %.1f -> %.1f" % (float(st.get("tickMs") or 0.0), r["tick_max"]))
    m.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

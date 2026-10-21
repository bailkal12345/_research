# -*- coding: utf-8 -*-
"""
Прогон с поднятым лимитом тиков.

Зачем: при штатном NetServerMaxTickRate = 30 GameThread простаивает 92% времени,
и метрика «тиков/с» упирается в потолок — улучшения не видно. Сняв потолок,
получаем чистую меру пропускной способности GameThread: сколько тиков мира он
реально способен отработать в секунду.

    python exp_tickrate.py [--steps 30,60,120,300,1000,200000]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import rcon  # noqa: E402
import threadcpu  # noqa: E402

LOG = r"C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi\Plugins\TickProf\TickProf.log"


def cmd(text, timeout=10):
    try:
        return rcon.rcon(text, timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        return "<%s>" % type(exc).__name__


def alive():
    try:
        rcon.rcon("plugins.list", timeout=5)
        return True
    except Exception:
        return False


def log_tail(n=60):
    try:
        with open(LOG, "r", encoding="utf-8", errors="replace") as f:
            return [ln.rstrip() for ln in f.readlines()[-n:]]
    except OSError:
        return []


def game_tid():
    for ln in reversed(log_tail(400)):
        if "game thread tid=" in ln:
            return int(ln.strip().split("tid=")[-1])
    return 0


def wait_ready(minutes=20):
    end = time.time() + minutes * 60
    while time.time() < end:
        if alive() and game_tid():
            return True
        time.sleep(6)
    return False


def cpu_of(tid, seconds=4):
    vals = []
    for _ in range(seconds):
        v = threadcpu.cpu_times(tid)
        if v is not None:
            vals.append(v)
        time.sleep(1.0)
    if len(vals) < 2:
        return 0.0
    return (vals[-1] - vals[0]) / (len(vals) - 1)


def measure(label, tid, seconds=30):
    c0 = cpu_of(tid, 3)
    cmd("TickProf.perf %d" % seconds)
    time.sleep(seconds + 5)
    c1 = cpu_of(tid, 3)
    frames, wall = 0, 0.0
    for ln in reversed(log_tail(60)):
        if "perf окно" in ln:
            for tok in ln.split():
                if tok.startswith("frames="):
                    frames = int(tok.split("=")[1])
                if tok.startswith("wall="):
                    wall = float(tok.split("=")[1].rstrip("s"))
            break
    tps = frames / wall if wall else 0.0
    cpu_per_tick = (1000.0 * c1 / tps) if tps else 0.0  # мс CPU на один тик
    print("   %-16s тиков/с %7.1f | cpu %.3f s/s | %.2f мс CPU на тик"
          % (label, tps, c1, cpu_per_tick), flush=True)
    return {"tps": tps, "cpu": c1, "per_tick_ms": cpu_per_tick, "alive": c1 > 0.005}


def show(keys, n=40):
    for ln in log_tail(n):
        if any(k in ln for k in keys):
            print("      " + ln.split(" ", 1)[-1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", default="30,60,120,300,1000,200000")
    ap.add_argument("--window", type=int, default=30)
    args = ap.parse_args()

    if not wait_ready():
        print("не готов")
        return 1
    tid = game_tid()
    print("game thread tid=%d" % tid, flush=True)

    results = []
    for step in [int(s) for s in args.steps.split(",")]:
        print("\n[лимит %s]" % step, flush=True)
        cmd("TickProf.maxfps %d" % step)
        time.sleep(4)
        show(("maxfps",))
        if not alive():
            print("   сервер не отвечает сразу после установки лимита")
            break
        r = measure("лимит=%d" % step, tid, args.window)
        if not r or not r["alive"]:
            print("   сервер не выжил на лимите %d" % step)
            break
        results.append((step, r))

    print("\n[итог по лимитам]", flush=True)
    print("   %-12s %10s %12s" % ("лимит", "тиков/с", "мс/тик"))
    for step, r in results:
        print("   %-12d %10.1f %12.2f" % (step, r["tps"], r["per_tick_ms"]))

    print("\n[возврат к штатному лимиту]", flush=True)
    cmd("TickProf.maxfps 0")
    time.sleep(4)
    show(("maxfps",))
    return 0


if __name__ == "__main__":
    sys.exit(main())
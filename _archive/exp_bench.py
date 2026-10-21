# -*- coding: utf-8 -*-
"""
Бенчмарк оптимизаций на снятом лимите тиков.

При лимите 30 GameThread простаивает, и метрика упирается в потолок.
При лимите 200000 узкое место — сам GameThread, поэтому «тиков/с» становится
чистой мерой: сколько тиков мира он способен отработать в секунду.

    python exp_bench.py [--limit 200000] [--window 30]
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


def cpu_of(tid, seconds=3):
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
    c0 = cpu_of(tid, 2)
    cmd("TickProf.perf %d" % seconds)
    time.sleep(seconds + 5)
    c1 = cpu_of(tid, 2)
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
    per_tick = 1000.0 * c1 / tps if tps else 0.0
    print("   %-22s тиков/с %7.1f | cpu %.3f s/s | %.2f мс/тик"
          % (label, tps, c1, per_tick), flush=True)
    return {"tps": tps, "cpu": c1, "per_tick": per_tick, "alive": c1 > 0.005}


def show(keys, n=40):
    for ln in log_tail(n):
        if any(k in ln for k in keys):
            print("      " + ln.split(" ", 1)[-1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=200000)
    ap.add_argument("--window", type=int, default=30)
    args = ap.parse_args()

    if not wait_ready():
        print("не готов")
        return 1
    tid = game_tid()
    print("game thread tid=%d" % tid, flush=True)

    print("\nснимаем лимит тиков: %d" % args.limit, flush=True)
    cmd("TickProf.maxfps %d" % args.limit)
    time.sleep(5)
    show(("maxfps",))

    # прогрев: первые окна ещё совпадают со стримингом мира
    print("\n[прогрев] 30 с", flush=True)
    measure("warmup", tid, 30)

    steps = [
        ("raw", [], "БЕЗ ОПТИМИЗАЦИЙ"),
        ("fncache", ["TickProf.fncache 1"], "кэш FindFunctionByName"),
        ("iscache", ["TickProf.iscache 1"], "кэш IsChildOf"),
        ("cachename", ["TickProf.cachename 1"], "кэш канвасов"),
        ("trim2", ["TickProf.overlaptrim 2"], "обрезка пересечений"),
    ]
    res = {}
    for key, cmds, label in steps:
        for c in cmds:
            cmd(c)
            time.sleep(4)
        if cmds:
            show(("cache", "overlaptrim", "canvas"))
        r = measure(label, tid, args.window)
        res[key] = r
        if not r or not r["alive"]:
            print("   сервер не выжил на шаге %s" % key)
            break

    print("\n[1] асинхронная физика", flush=True)
    cmd("p.bTickPhysicsAsync 1")
    time.sleep(6)
    r = measure("асинхронная физика", tid, args.window)
    res["async"] = r

    print("\n[2] асинхронные тики (патч + разметка)", flush=True)
    cmd("TickProf.fix concurrent 1")
    time.sleep(4)
    cmd("TickProf.tickflags 2")
    time.sleep(8)
    show(("concurrent", "tickflags"))
    r2 = measure("асинхронные тики", tid, args.window)
    res["asynctick"] = r2
    cmd("TickProf.tickflags 0")
    cmd("TickProf.fix concurrent 0")
    time.sleep(4)

    print("\n[итог]", flush=True)
    base = res.get("raw", {}).get("tps") or 0.0
    print("   %-24s %10s %12s %10s" % ("вариант", "тиков/с", "мс/тик", "к базе"))
    for key, cmds, label in steps:
        r = res.get(key)
        if not r:
            continue
        d = ("%+.0f%%" % (100.0 * (r["tps"] - base) / base)) if base else ""
        print("   %-24s %10.1f %12.2f %10s" % (label, r["tps"], r["per_tick"], d))
    for key, label in (("async", "асинхронная физика"), ("asynctick", "асинхронные тики")):
        r = res.get(key)
        if not r:
            continue
        d = ("%+.0f%%" % (100.0 * (r["tps"] - base) / base)) if base else ""
        print("   %-24s %10.1f %12.2f %10s" % (label, r["tps"], r["per_tick"], d))

    print("\n[возврат]", flush=True)
    cmd("p.bTickPhysicsAsync 0")
    time.sleep(4)
    return 0


if __name__ == "__main__":
    sys.exit(main())
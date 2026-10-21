# -*- coding: utf-8 -*-
"""
Вариант 4: асинхронная физика.

p.bTickPhysicsAsync — штатный переключатель UE4.5, который уводит тик PhysX
с GameThread на воркер. Это единственный оставшийся механизм параллелизма,
который движок поддерживает без патчей.

    python exp_phase4.py
"""
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


def cpu_of(tid, seconds=5):
    vals = []
    for _ in range(seconds):
        v = threadcpu.cpu_times(tid)
        if v is not None:
            vals.append(v)
        time.sleep(1.0)
    if len(vals) < 2:
        return 0.0
    return (vals[-1] - vals[0]) / (len(vals) - 1)


def measure(label, tid, seconds=40):
    c0 = cpu_of(tid, 3)
    cmd("TickProf.perf %d" % seconds)
    time.sleep(seconds + 6)
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
    print("   %-22s cpu %.3f->%.3f s/s | тиков/с %.1f" % (label, c0, c1, tps), flush=True)
    return {"cpu": (c0 + c1) / 2.0, "tps": tps, "alive": c1 > 0.005}


def show(keys, n=60):
    for ln in log_tail(n):
        if any(k in ln for k in keys):
            print("      " + ln.split(" ", 1)[-1])


def main():
    tid = game_tid()
    if not tid:
        print("нет game thread")
        return 1
    print("game thread tid=%d" % tid, flush=True)

    print("\n[1] штатное состояние + наши правки", flush=True)
    cmd("TickProf.cachename 1")
    time.sleep(4)
    cmd("TickProf.overlaptrim 8")
    time.sleep(15)
    show(("canvas", "overlaptrim"))
    base = measure("BASE", tid, 40)

    print("\n[2] асинхронная физика", flush=True)
    print("   > %s" % cmd("p.bTickPhysicsAsync 1"))
    time.sleep(10)
    async_phys = measure("ASYNC_PHYSICS", tid, 40)
    if async_phys and not async_phys["alive"]:
        print("   сервер не выжил с асинхронной физикой")
        return 2

    print("\n[3] асинхронная физика + патч + разметка тиков", flush=True)
    cmd("TickProf.fix concurrent 1")
    time.sleep(5)
    cmd("TickProf.tickflags 2")
    time.sleep(10)
    show(("concurrent", "tickflags mode"))
    both = measure("ASYNC+PATCH+FLAGS", tid, 40)
    if both and not both["alive"]:
        print("   сервер не выжил")
        return 3

    print("\n[4] возврат", flush=True)
    cmd("TickProf.tickflags 0")
    cmd("TickProf.fix concurrent 0")
    cmd("p.bTickPhysicsAsync 0")
    time.sleep(8)
    measure("CLEANUP", tid, 30)

    print("\n[итог]", flush=True)
    for name, r in (("base", base), ("async_phys", async_phys), ("async+patch+flags", both)):
        if r:
            print("   %-18s cpu=%.3f s/s  тиков/с=%.1f" % (name, r["cpu"], r["tps"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""
Решающий эксперимент: поднимаем лимит тиков, чтобы GameThread стал узким местом,
и только тогда проверяем вклад патча bAllowConcurrentTicks и флага bRunOnAnyThread.

    python exp_phase3.py
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
    perf = ""
    for ln in reversed(log_tail(60)):
        if "perf окно" in ln:
            perf = ln.split("perf окно:")[-1].strip()
            break
    print("   %-22s cpu %.3f->%.3f | %s" % (label, c0, c1, perf or "нет данных"), flush=True)
    return {"cpu": (c0 + c1) / 2.0, "perf": perf, "alive": c1 > 0.005}


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

    print("\n[1] вернуть штатное состояние", flush=True)
    cmd("TickProf.cachename 1")
    cmd("TickProf.overlaptrim 8")
    cmd("TickProf.fix concurrent 0")
    cmd("TickProf.tickflags 0")
    time.sleep(8)
    show(("concurrent", "overlaptrim", "canvas"))

    print("\n[2] baseline на штатном лимите тиков", flush=True)
    measure("BASELINE_30", tid, 40)

    print("\n[3] поднимаем лимит тиков", flush=True)
    print("   > %s" % cmd("net.MaxNetTickRate 300"))
    time.sleep(8)
    m = measure("TICKRATE_300_OFF", tid, 40)
    if m and not m["alive"]:
        return 2

    print("\n[4] патч включён, флагов нет", flush=True)
    cmd("TickProf.fix concurrent 1")
    time.sleep(6)
    show(("concurrent",))
    m = measure("PATCH_ONLY", tid, 40)
    if m and not m["alive"]:
        return 3

    print("\n[5] патч выключен, флаги включены (контроль: флаг без патча)", flush=True)
    cmd("TickProf.fix concurrent 0")
    cmd("TickProf.tickflags 2")
    time.sleep(10)
    show(("tickflags mode",))
    m = measure("FLAGS_NO_PATCH", tid, 40)
    if m and not m["alive"]:
        return 4

    print("\n[6] патч включён + флаги включены", flush=True)
    cmd("TickProf.fix concurrent 1")
    time.sleep(6)
    show(("concurrent",))
    m = measure("PATCH_AND_FLAGS", tid, 40)
    if m and not m["alive"]:
        print("   сервер не выжил с асинхронными тиками")
        return 5

    print("\n[7] флаги на всех тик-функциях (mode 5)", flush=True)
    cmd("TickProf.tickflags 5")
    time.sleep(10)
    show(("tickflags mode",))
    m = measure("PATCH_AND_FLAGS_ALL", tid, 40)
    if m and not m["alive"]:
        print("   сервер не выжил с mode 5")
        return 6

    print("\n[8] возврат", flush=True)
    cmd("TickProf.tickflags 0")
    cmd("TickProf.fix concurrent 0")
    time.sleep(5)
    measure("AFTER_CLEANUP", tid, 30)
    return 0


if __name__ == "__main__":
    sys.exit(main())
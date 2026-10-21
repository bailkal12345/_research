# -*- coding: utf-8 -*-
"""
Фаза 2: реальные исправления, каждый проверяется замером GameThread.

    python exp_phase2.py

Порядок: перепись пересечений -> baseline -> кэш канвасов -> обрезка
перегруженных компонентов -> патч bAllowConcurrentTicks -> разметка тиков.
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


def wait_ready(minutes=20):
    end = time.time() + minutes * 60
    while time.time() < end:
        try:
            rcon.rcon("plugins.list", timeout=4)
            if game_tid():
                return True
        except Exception:
            pass
        time.sleep(6)
    return False


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
    if not tid:
        return None
    c0 = cpu_of(tid, 3)
    cmd("TickProf.perf %d" % seconds)
    time.sleep(seconds + 6)
    c1 = cpu_of(tid, 3)
    perf = ""
    for ln in reversed(log_tail(60)):
        if "perf окно" in ln:
            perf = ln.split("perf окно:")[-1].strip()
            break
    print("   %-18s cpu %.3f -> %.3f s/s | %s" % (label, c0, c1, perf or "нет данных"), flush=True)
    return {"cpu": (c0 + c1) / 2.0, "perf": perf, "alive": c1 > 0.005}


def show(keys, n=120):
    for ln in log_tail(n):
        if any(k in ln for k in keys):
            print("      " + ln.split(" ", 1)[-1])


def main():
    if not wait_ready():
        print("не готов")
        return 1
    tid = game_tid()
    print("game thread tid=%d" % tid, flush=True)

    print("\n[1] census пересечений", flush=True)
    cmd("TickProf.overlapsizes")
    time.sleep(12)
    show(("overlapsizes",))

    results = {}
    print("\n[2] baseline", flush=True)
    results["baseline"] = measure("BASELINE", tid, 40)

    print("\n[3] кэш Kismet-канвасов", flush=True)
    cmd("TickProf.cachename 1")
    time.sleep(6)
    show(("canvas",))
    results["canvas"] = measure("CANVAS", tid, 40)
    if results["canvas"] and not results["canvas"]["alive"]:
        return 3

    print("\n[4] обрезка перегруженных компонентов (порог 32)", flush=True)
    cmd("TickProf.overlaptrim 32")
    time.sleep(12)
    show(("overlaptrim",))
    results["trim32"] = measure("TRIM_32", tid, 40)
    if results["trim32"] and not results["trim32"]["alive"]:
        return 4

    print("\n[5] порог 8", flush=True)
    cmd("TickProf.overlaptrim 8")
    time.sleep(12)
    show(("overlaptrim",))
    results["trim8"] = measure("TRIM_8", tid, 40)
    if results["trim8"] and not results["trim8"]["alive"]:
        return 5

    print("\n[6] патч bAllowConcurrentTicks (A/B/A)", flush=True)
    cmd("TickProf.fix concurrent 1")
    time.sleep(6)
    show(("concurrent",))
    results["patch_A"] = measure("PATCH_A", tid, 40)
    if results["patch_A"] and not results["patch_A"]["alive"]:
        return 6
    cmd("TickProf.fix concurrent 0")
    time.sleep(6)
    show(("concurrent",))
    results["patch_B"] = measure("PATCH_OFF", tid, 40)

    for mode, desc in ((4, "тики акторов"), (2, "компоненты TG_DuringPhysics")):
        cmd("TickProf.tickflags %d" % mode)
        time.sleep(10)
        show(("tickflags mode",))
        r = measure("FLAGS_%d" % mode, tid, 40)
        results["mode%d" % mode] = r
        if r and not r["alive"]:
            print("   сервер пал на режиме %d" % mode)
            return 7
        cmd("TickProf.tickflags 0")
        time.sleep(3)

    print("\n[итог]", flush=True)
    for k, v in results.items():
        if v:
            print("   %-10s cpu=%.3f s/s" % (k, v["cpu"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
# -*- coding: utf-8 -*-
"""
Цикл 5: новые правки из анализа профиля и дампа ARK.

  1) кэш UClass::FindFunctionByName   (2.3% профиля)
  2) обрезка пересечений, порог 2      (остаток 8.5% профиля)
  3) полное отключение overlap-событий (предельный режим)
  4) асинхронная физика p.bTickPhysicsAsync

    python exp_cycle5.py
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


def measure(label, tid, seconds=35):
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
    print("   %-24s cpu %.3f->%.3f s/s | тиков/с %.1f" % (label, c0, c1, tps), flush=True)
    return {"cpu": (c0 + c1) / 2.0, "tps": tps, "alive": c1 > 0.005}


def show(keys, n=80):
    for ln in log_tail(n):
        if any(k in ln for k in keys):
            print("      " + ln.split(" ", 1)[-1])


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


def main():
    if not wait_ready():
        print("сервер/плагин не готовы")
        return 1
    tid = game_tid()
    if not tid:
        print("нет game thread")
        return 1
    print("game thread tid=%d" % tid, flush=True)
    res = {}

    print("\n[0] базовое состояние: canvas-кэш + обрезка 8", flush=True)
    cmd("TickProf.cachename 1")
    time.sleep(3)
    cmd("TickProf.fncache 0")
    cmd("TickProf.overlapall 0")
    cmd("TickProf.overlaptrim 8")
    time.sleep(12)
    show(("canvas", "overlaptrim", "fncache", "overlapall"))
    res["base"] = measure("BASE(trim8)", tid, 35)

    print("\n[1] кэш UClass::FindFunctionByName", flush=True)
    cmd("TickProf.fncache 1")
    time.sleep(5)
    show(("fncache",))
    res["fncache"] = measure("+FNCACHE", tid, 35)
    if res["fncache"] and not res["fncache"]["alive"]:
        return 2

    print("\n[2] обрезка пересечений, порог 2", flush=True)
    cmd("TickProf.overlaptrim 2")
    time.sleep(12)
    show(("overlaptrim",))
    res["trim2"] = measure("+TRIM2", tid, 35)
    if res["trim2"] and not res["trim2"]["alive"]:
        return 3

    print("\n[3] обрезка пересечений, порог 1", flush=True)
    cmd("TickProf.overlaptrim 1")
    time.sleep(12)
    show(("overlaptrim",))
    res["trim1"] = measure("+TRIM1", tid, 35)
    if res["trim1"] and not res["trim1"]["alive"]:
        return 4

    print("\n[4] предельный режим: отключить все overlap-события", flush=True)
    cmd("TickProf.overlapall 1")
    time.sleep(12)
    show(("overlapall",))
    res["overlapall"] = measure("+OVERLAPALL", tid, 35)
    if res["overlapall"] and not res["overlapall"]["alive"]:
        return 5

    print("\n[5] вернуть overlap, асинхронная физика", flush=True)
    cmd("TickProf.overlapall 0")
    time.sleep(6)
    print("   > %s" % cmd("p.bTickPhysicsAsync 1"))
    time.sleep(10)
    res["asyncphys"] = measure("+ASYNC_PHYSICS", tid, 35)
    if res["asyncphys"] and not res["asyncphys"]["alive"]:
        return 6
    cmd("p.bTickPhysicsAsync 0")
    time.sleep(6)

    print("\n[итог]", flush=True)
    prev = None
    for k in ("base", "fncache", "trim2", "trim1", "overlapall", "asyncphys"):
        r = res.get(k)
        if not r:
            continue
        delta = ""
        if prev:
            delta = "  (%+.1f%%)" % (100.0 * (r["cpu"] - prev) / prev if prev else 0.0)
        print("   %-12s cpu=%.3f s/s  тиков/с=%.1f%s" % (k, r["cpu"], r["tps"], delta))
        prev = r["cpu"]
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""
Финальный замер: чистый старт -> базовая линия -> применяем доказанные правки
-> контрольный профиль GameThread.

    python exp_final.py
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import rcon  # noqa: E402
import threadcpu  # noqa: E402

LOG = r"C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi\Plugins\TickProf\TickProf.log"
PDIR = r"C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi\Plugins\TickProf"


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
    c0 = cpu_of(tid, 3)
    cmd("TickProf.perf %d" % seconds)
    time.sleep(seconds + 6)
    c1 = cpu_of(tid, 3)
    frames = 0
    wall = 0.0
    for ln in reversed(log_tail(60)):
        if "perf окно" in ln:
            for tok in ln.split():
                if tok.startswith("frames="):
                    frames = int(tok.split("=")[1])
                if tok.startswith("wall="):
                    wall = float(tok.split("=")[1].rstrip("s"))
            break
    tps = frames / wall if wall else 0
    print("   %-20s cpu %.3f->%.3f s/s | тиков/с %.1f" % (label, c0, c1, tps), flush=True)
    return {"cpu": (c0 + c1) / 2.0, "tps": tps, "alive": c1 > 0.005}


def show(keys, n=60):
    for ln in log_tail(n):
        if any(k in ln for k in keys):
            print("      " + ln.split(" ", 1)[-1])


def main():
    if not wait_ready():
        print("не готов")
        return 1
    tid = game_tid()
    print("game thread tid=%d" % tid, flush=True)

    print("\n[1] профиль ДО правок (90 с)", flush=True)
    cmd("TickProf.start 90")
    time.sleep(100)
    print("\n[2] линия ДО правок", flush=True)
    before = measure("BEFORE", tid, 40)

    print("\n[3] применяем доказанные правки", flush=True)
    cmd("TickProf.cachename 1")
    time.sleep(4)
    cmd("TickProf.overlaptrim 8")
    time.sleep(15)
    show(("canvas", "overlaptrim"))

    after = measure("AFTER", tid, 40)

    print("\n[4] профиль ПОСЛЕ правок (90 с)", flush=True)
    cmd("TickProf.start 90")
    time.sleep(100)

    print("\n[итог]", flush=True)
    if before and after:
        print("   CPU  %.3f -> %.3f s/s  (−%.0f%%)" % (before["cpu"], after["cpu"],
              100.0 * (before["cpu"] - after["cpu"]) / before["cpu"] if before["cpu"] else 0))
        print("   тиков/с %.1f -> %.1f" % (before["tps"], after["tps"]))

    print("\n[5] артефакты", flush=True)
    for f in sorted(os.listdir(PDIR)):
        if f.startswith("prof_"):
            print("   %s (%d байт)" % (f, os.path.getsize(os.path.join(PDIR, f))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
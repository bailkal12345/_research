# -*- coding: utf-8 -*-
"""
Очередь тик-задач: перепись тикающих компонентов и отключение ненужных.

Замер фаз показал, что FTickTaskManager::StartFrame стоит 3.05 мс на кадр (34%
времени кадра) — это постановка в очередь тик-функций. Поэтому главный рычаг —
число тикающих компонентов.

    python exp_tickqueue.py
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


def alive():
    try:
        rcon.rcon("plugins.list", timeout=5)
        return True
    except Exception:
        return False


def log_tail(n=80):
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


def measure(label, tid, seconds=25):
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
    print("   %-30s тиков/с %7.1f | cpu %.3f s/s | %.2f мс/тик"
          % (label, tps, c1, 1000.0 * c1 / tps if tps else 0), flush=True)
    return {"tps": tps, "cpu": c1, "alive": c1 > 0.005}


def show(keys, n=100):
    for ln in log_tail(n):
        if any(k in ln for k in keys):
            print("      " + ln.split(" ", 1)[-1])


def main():
    if not wait_ready():
        print("не готов")
        return 1
    tid = game_tid()
    print("game thread tid=%d" % tid, flush=True)

    cmd("TickProf.maxfps 200000")
    time.sleep(5)
    print("\n[1] прогрев", flush=True)
    time.sleep(25)
    base = measure("база (кэши выкл)", tid, 25)

    print("\n[2] все кэши", flush=True)
    for c in ("TickProf.fncache 1", "TickProf.iscache 1", "TickProf.cachename 1"):
        cmd(c)
        time.sleep(3)
    cmd("TickProf.overlaptrim 2")
    time.sleep(12)
    cached = measure("с кэшами", tid, 25)

    print("\n[3] перепись тикающих компонентов", flush=True)
    cmd("TickProf.tickclasses")
    time.sleep(15)
    show(("tickclasses", "   "))

    print("\n[4] отключение тика у декоративных компонентов", flush=True)
    for pattern in ("StaticMesh", "Landscape", "Foliage", "Decorative", "Spline"):
        cmd("TickProf.tickoff %s" % pattern)
        time.sleep(6)
    show(("tickoff",))
    off = measure("без декоративных тиков", tid, 25)

    print("\n[5] фазовые таймеры", flush=True)
    for h in range(0, 5):
        cmd("TickProf.hook %d" % h)
    time.sleep(8)
    cmd("TickProf.start 25")
    time.sleep(38)

    print("\n[итог]", flush=True)
    for label, r in (("база", base), ("с кэшами", cached), ("без декоративных", off)):
        if r:
            print("   %-22s тиков/с %7.1f  мс/тик %.2f" % (label, r["tps"], 1000.0 * r["cpu"] / r["tps"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
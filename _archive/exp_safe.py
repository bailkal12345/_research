# -*- coding: utf-8 -*-
"""
Финальный безопасный прогон: только проверенные правки.

Исключено намеренно:
  * TickProf.cull          — роняет сервер (проверено);
  * plugins.unload         — вешает сервер при активных фазовых хуках;
  * TickProf.overlapall    — ломает игровые механики;
  * патч асинхронных тиков — замедляет.

    python exp_safe.py
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("RCON_HOST", "192.168.8.218")
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


def measure(label, tid, seconds=30):
    c0 = cpu_of(tid, 4)
    cmd("TickProf.perf %d" % seconds)
    time.sleep(seconds + 5)
    c1 = cpu_of(tid, 4)
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
    ms = 1000.0 * c1 / tps if tps else 0.0
    print("   %-28s тиков/с %5.1f | cpu %.3f s/s | %.2f мс CPU на тик"
          % (label, tps, c1, ms), flush=True)
    return {"cpu": c1, "ms": ms, "tps": tps, "alive": c1 > 0.005}


def show(keys, n=50):
    for ln in log_tail(n):
        if any(k in ln for k in keys):
            print("      " + ln.split(" ", 1)[-1])


def main():
    if not wait_ready():
        print("сервер не готов")
        return 1
    tid = game_tid()
    print("game thread tid=%d" % tid, flush=True)

    print("\n[0] проверка защиты cull", flush=True)
    cmd("TickProf.cull 15000")
    time.sleep(4)
    show(("cull",))
    if not alive():
        print("   что-то пошло не так")
        return 2

    print("\n[1] базовая линия (пусто)", flush=True)
    base = measure("БАЗА", tid, 30)

    print("\n[2] кэши", flush=True)
    for c in ("TickProf.fncache 1", "TickProf.iscache 1", "TickProf.cachename 1"):
        cmd(c)
        time.sleep(3)
    caches = measure("КЭШИ", tid, 30)

    print("\n[3] обрезка пересечений", flush=True)
    cmd("TickProf.overlaptrim 2")
    time.sleep(15)
    show(("overlaptrim",))
    trim = measure("+ОБРЕЗКА", tid, 30)

    print("\n[4] отключение статистики FPS", flush=True)
    cmd("TickProf.nochart 1")
    time.sleep(5)
    show(("nochart",))
    nochart = measure("+NOCHART", tid, 30)
    if not nochart["alive"]:
        print("   сервер не выжил — откатываем")
        cmd("TickProf.nochart 0")
        return 3

    print("\n[5] контрольный профиль (60 с)", flush=True)
    cmd("TickProf.start 60")
    time.sleep(75)

    print("\n[итог]", flush=True)
    ref = base["ms"] if base else 0
    for label, r in (("база", base), ("кэши", caches), ("+обрезка", trim), ("+nochart", nochart)):
        if not r:
            continue
        d = ("  %+.1f%%" % (100.0 * (r["ms"] - ref) / ref)) if ref else ""
        print("   %-10s %.3f s/s | %.2f мс/тик%s" % (label, r["cpu"], r["ms"], d))
    print("\nсервер жив:", alive())
    return 0


if __name__ == "__main__":
    sys.exit(main())
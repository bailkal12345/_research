# -*- coding: utf-8 -*-
"""
Полный цикл экспериментов: перепись -> патч -> разметка тиков -> кэш канвасов ->
census overlap-событий. Каждый шаг снимает внутрипроцессный замер GameThread.

    python exp_cycle.py
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


def wait_ready(minutes=15):
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


def cpu_of(tid, seconds=6):
    vals = []
    for _ in range(seconds):
        v = threadcpu.cpu_times(tid)
        if v is not None:
            vals.append(v)
        time.sleep(1.0)
    if len(vals) < 2:
        return 0.0
    return (vals[-1] - vals[0]) / (len(vals) - 1)


def new_lines(before, keys=()):
    out = []
    for ln in log_tail(80)[max(0, len(log_tail(80)) - 80):]:
        pass
    for ln in log_tail(80):
        if any(k in ln for k in keys):
            out.append(ln.split(" ", 1)[-1])
    return out


def measure(label, tid, seconds=45):
    if not tid:
        print("   %-20s нет game thread" % label)
        return None
    c0 = cpu_of(tid, 3)
    cmd("TickProf.perf %d" % seconds)
    time.sleep(seconds + 6)
    c1 = cpu_of(tid, 3)
    alive = c1 > 0.005
    perf = ""
    for ln in reversed(log_tail(60)):
        if "perf окно" in ln:
            perf = ln.split("perf окно:")[-1].strip()
            break
    print("   %-20s cpu %.3f->%.3f s/s | %s" % (label, c0, c1, perf or "нет данных"), flush=True)
    return {"cpu0": c0, "cpu1": c1, "perf": perf, "alive": alive}


def show(keys, n=80):
    for ln in log_tail(n):
        if any(k in ln for k in keys):
            print("      " + ln.split(" ", 1)[-1])


def main():
    if not wait_ready():
        print("сервер/плагин не готовы")
        return 1
    tid = game_tid()
    print("game thread tid=%d" % tid, flush=True)

    print("\n[1] перепись тик-функций", flush=True)
    cmd("TickProf.ticklist")
    time.sleep(10)
    show(("ticklist",))

    print("\n[2] baseline", flush=True)
    base = measure("BASELINE", tid, 45)
    if base and not base["alive"]:
        return 2

    print("\n[3] патч bAllowConcurrentTicks", flush=True)
    cmd("TickProf.fix concurrent 1")
    time.sleep(6)
    show(("concurrent", "verify"))
    patch = measure("PATCH_ONLY", tid, 45)
    if patch and not patch["alive"]:
        print("   сервер пал после патча")
        return 3

    print("\n[4] census overlap-событий (30 с)", flush=True)
    cmd("TickProf.overlaps 30")
    time.sleep(38)
    cmd("TickProf.overlapsreport")
    time.sleep(10)
    show(("overlaps",))

    print("\n[5] кэш Kismet-канвасов", flush=True)
    cmd("TickProf.cachename 1")
    time.sleep(6)
    show(("canvas",))
    canvas = measure("CANVAS_CACHE", tid, 45)
    if canvas and not canvas["alive"]:
        print("   сервер пал на кэше канвасов")
        return 4

    print("\n[6] разметка тик-функций (patch + canvas + flags)", flush=True)
    for mode, desc in ((4, "тики акторов"), (2, "компоненты TG_DuringPhysics"), (5, "все без prereq")):
        cmd("TickProf.tickflags %d" % mode)
        time.sleep(8)
        show(("tickflags mode",))
        m = measure("MODE_%d" % mode, tid, 40)
        if m and not m["alive"]:
            print("   сервер пал на режиме %d (%s)" % (mode, desc))
            return 5
        cmd("TickProf.tickflags 0")
        time.sleep(3)

    return 0


if __name__ == "__main__":
    sys.exit(main())
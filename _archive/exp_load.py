# -*- coding: utf-8 -*-
"""
Создание нагрузки и проверка, что сервер переживает спавн.

    python exp_load.py

Шаги: спавн 5 -> 25 -> 100 -> 200 динозавров, после каждого контроль GameThread.
Без устойчивого спавна измерения эффекта патча не видно: без игроков GameThread
занят на 7% и любой выигрыш тонет в шуме.
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


def log_tail(n=40):
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


def show(tag, n=8):
    for ln in log_tail(n):
        if any(k in ln for k in ("spawn", "dino", "overlap", "canvas", "ticklist", "perf", "concurrent")):
            print("   | %s" % ln.split(" ", 1)[-1])


def main():
    tid = game_tid()
    print("game thread tid=%d" % tid)
    if not tid:
        return 1

    base = cpu_of(tid, 8)
    print("базовая загрузка: %.3f s/s" % base)

    print("\n-- перепись тик-функций --")
    cmd("TickProf.ticklist")
    time.sleep(8)
    show("", 20)

    for n in (5, 25, 100, 200):
        print("\n-- спавн %d динозавров --" % n)
        print("   > %s" % cmd("TickProf.spawn %d" % n))
        time.sleep(20)
        show("", 12)
        c = cpu_of(tid, 8)
        print("   GameThread cpu=%.3f s/s %s" % (c, "" if c > 0.01 else "<-- МЁРТВ"))
        if c <= 0.01:
            print("   сервер пал на спавне %d" % n)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
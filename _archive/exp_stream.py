# -*- coding: utf-8 -*-
"""
Эксперимент: патч bAllowConcurrentTicks + разметка тик-функций.

Запускается сразу после старта сервера, пока идёт фаза стриминга мира —
иначе на сервере без игроков GameThread загружен на 7% и разницу не видно.

    python exp_stream.py
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import rcon  # noqa: E402
import threadcpu  # noqa: E402

LOG = r"C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi\Plugins\TickProf\TickProf.log"


def cmd(text, timeout=8):
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


def wait_rcon(minutes=12):
    end = time.time() + minutes * 60
    while time.time() < end:
        if threadcpu.find_pid():
            try:
                rcon.rcon("plugins.list", timeout=4)
                return True
            except Exception:
                pass
        time.sleep(5)
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


def measure(label, seconds=60):
    """Окно внутрипроцессного замера + независимая проверка по CPU потока."""
    tid = game_tid()
    c0 = cpu_of(tid, 2)
    cmd("TickProf.perf %d" % seconds)
    time.sleep(seconds + 5)
    c1 = cpu_of(tid, 2)
    for ln in reversed(log_tail(60)):
        if "perf окно" in ln:
            print("   %-22s %s" % (label, ln.split("perf окно:")[-1].strip()), flush=True)
            print("   %-22s внешний CPU: %.3f -> %.3f s/s" % ("", c0, c1), flush=True)
            return True
    print("   %-22s отчёт не получен (cpu %.3f -> %.3f)" % (label, c0, c1), flush=True)
    return False


def main():
    if not wait_rcon():
        print("сервер не поднялся")
        return 1
    tid = game_tid()
    if not tid:
        print("плагин не сообщил game thread")
        return 1
    print("game thread tid=%d" % tid, flush=True)

    print("\n--- фаза стриминга: базовая линия", flush=True)
    measure("BASELINE", 60)

    print("\n--- перепись тик-функций", flush=True)
    cmd("TickProf.ticklist")
    time.sleep(6)
    for ln in reversed(log_tail(20)):
        if "ticklist" in ln:
            print("   " + ln.split(" ", 1)[-1])
    cmd("TickProf.verify")
    time.sleep(4)
    for ln in reversed(log_tail(20)):
        if "verify" in ln:
            print("   " + ln.split(" ", 1)[-1])

    print("\n--- патч bAllowConcurrentTicks = true", flush=True)
    print("   > %s" % cmd("TickProf.fix concurrent 1"), flush=True)
    time.sleep(4)
    for ln in reversed(log_tail(20)):
        if "concurrent" in ln:
            print("   " + ln.split(" ", 1)[-1])
    cmd("TickProf.verify")
    time.sleep(4)
    for ln in reversed(log_tail(20)):
        if "verify" in ln:
            print("   " + ln.split(" ", 1)[-1])

    c = cpu_of(tid, 6)
    print("   GameThread cpu=%.3f s/s" % c, flush=True)
    measure("PATCH_ONLY", 60)

    for mode, desc in ((4, "тики акторов"), (2, "компоненты TG_DuringPhysics"), (5, "все без prereq")):
        print("\n--- tickflags mode=%d (%s)" % (mode, desc), flush=True)
        cmd("TickProf.tickflags %d" % mode)
        time.sleep(6)
        for ln in reversed(log_tail(20)):
            if "tickflags mode" in ln:
                print("   " + ln.split(" ", 1)[-1])
        c = cpu_of(tid, 5)
        print("   GameThread cpu=%.3f s/s %s" % (c, "" if c > 0.01 else "<-- МЁРТВ"), flush=True)
        if c <= 0.01:
            print("   сервер пал на этом режиме")
            break
        measure("MODE_%d" % mode, 45)
        cmd("TickProf.tickflags 0")
        time.sleep(3)

    return 0


if __name__ == "__main__":
    sys.exit(main())
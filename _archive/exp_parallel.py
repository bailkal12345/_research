# -*- coding: utf-8 -*-
"""
Прогон экспериментов по параллелизации GameThread.

    python exp_parallel.py [--only patch|tickflags]

Каждый шаг: состояние -> команда -> замер GameThread (внутрипроцессный perf) ->
контроль живости сервера. Шаг считается проваленным, если GameThread умер.
"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import rcon  # noqa: E402
import threadcpu  # noqa: E402

PLUGIN_DIR = r"C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi\Plugins\TickProf"
LOG = os.path.join(PLUGIN_DIR, "TickProf.log")


def cmd(text, timeout=8):
    try:
        return rcon.rcon(text, timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        return "<%s>" % type(exc).__name__


def log_tail(n=6):
    try:
        with open(LOG, "r", encoding="utf-8", errors="replace") as f:
            return [ln.rstrip() for ln in f.readlines()[-n:]]
    except OSError:
        return []


def game_tid():
    # берём ПОСЛЕДНЕЕ вхождение: лог переживает перезапуски сервера
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


def alive(tid, floor=0.02):
    c = cpu_of(tid, 5)
    return c, c >= floor


def perf(label, seconds=25):
    """Внутрипроцессный замер: frames, wall, cpu, доля занятости."""
    before = len(log_tail(1000))
    cmd("TickProf.perf %d" % seconds)
    time.sleep(seconds + 6)
    lines = log_tail(60)
    for ln in lines:
        if "perf окно" in ln:
            print("   %s | %s" % (label, ln.split("perf окно:")[-1].strip()))
            return ln
    print("   %s | отчёт не получен" % label)
    return ""


def step(name, rcon_cmds, tid, seconds=25):
    print("\n=== %s ===" % name, flush=True)
    for c in rcon_cmds:
        print("   > %s -> %s" % (c, cmd(c)), flush=True)
        time.sleep(3)
    for ln in log_tail(4):
        if any(k in ln for k in ("concurrent", "tickflags", "verify")):
            print("   | %s" % ln.split(" ", 1)[-1])
    c, ok = alive(tid)
    print("   GameThread cpu=%.3f s/s -> %s" % (c, "ЖИВ" if ok else "МЁРТВ"), flush=True)
    if not ok:
        return False
    perf(name, seconds)
    c2, _ = alive(tid, 0.01)
    print("   после замера cpu=%.3f s/s" % c2)
    return True


def main():
    only = None
    if "--only" in sys.argv:
        only = sys.argv[sys.argv.index("--only") + 1]

    tid = game_tid()
    if not tid:
        print("не найден game thread; сервер должен быть запущен и плагин загружен")
        return 1
    print("game thread tid=%d" % tid)

    base, ok = alive(tid)
    print("базовая загрузка GameThread: %.3f s/s -> %s" % (base, "ЖИВ" if ok else "МЁРТВ"))
    if not ok:
        return 2
    perf("BASELINE", 25)

    if only in (None, "patch"):
        if not step("PATCH bAllowConcurrentTicks=true", ["TickProf.fix concurrent 1", "TickProf.verify"], tid):
            return 3
        perf("PATCH_ONLY", 25)

    if only in (None, "tickflags"):
        for mode, desc in ((4, "только тики акторов"), (2, "компоненты TG_DuringPhysics без prereq"),
                           (5, "все без prerequisites"), (1, "вообще все")):
            if not step("TICKFLAGS mode=%d (%s)" % (mode, desc), ["TickProf.tickflags %d" % mode], tid, seconds=20):
                return 4
            cmd("TickProf.tickflags 0")
            time.sleep(2)

    return 0


if __name__ == "__main__":
    sys.exit(main())
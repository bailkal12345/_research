# -*- coding: utf-8 -*-
"""
Проверка безопасности p.bTickPhysicsAsync: включение в одиночку и контроль
отзывчивости. Предыдущий прогон показал, что после этой команды сервер
перестал отвечать — нужно отделить причину от совпадения.

    python exp_asyncphys.py
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
    """Отвечает ли сервер."""
    try:
        rcon.rcon("plugins.list", timeout=5)
        return True
    except Exception:
        return False


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
        if alive() and game_tid():
            return True
        time.sleep(6)
    return False


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


def watch(label, seconds=60):
    """Наблюдение за отзывчивостью: опрос RCON каждые 5 с."""
    t0 = time.time()
    bad = 0
    while time.time() - t0 < seconds:
        if not alive():
            bad += 1
            print("      %s: RCON не отвечает (%.0f с)" % (label, time.time() - t0), flush=True)
        else:
            bad = 0
        if bad >= 3:
            return False
        time.sleep(5)
    return True


def main():
    if not wait_ready():
        print("не готов")
        return 1
    tid = game_tid()
    print("game thread tid=%d" % tid, flush=True)

    print("\n[1] базовая конфигурация (проверенные правки)", flush=True)
    for c in ("TickProf.fncache 1", "TickProf.iscache 1", "TickProf.cachename 1"):
        cmd(c)
    time.sleep(5)
    cmd("TickProf.overlaptrim 2")
    time.sleep(12)
    c0 = cpu_of(tid, 8)
    print("   CPU до включения физики: %.3f s/s" % c0, flush=True)

    print("\n[2] контроль: сервер жив 30 с без изменений", flush=True)
    ok = watch("control", 30)
    print("   -> %s" % ("жив" if ok else "ЗАВИС"), flush=True)
    if not ok:
        return 2

    print("\n[3] p.bTickPhysicsAsync 1", flush=True)
    print("   > %s" % cmd("p.bTickPhysicsAsync 1"), flush=True)
    ok = watch("async", 60)
    print("   -> %s" % ("жив" if ok else "ЗАВИС"), flush=True)
    c1 = cpu_of(tid, 6) if ok else 0.0
    print("   CPU при асинхронной физике: %.3f s/s" % c1, flush=True)

    if ok:
        print("\n[4] вернуть обратно", flush=True)
        cmd("p.bTickPhysicsAsync 0")
        time.sleep(6)
        ok2 = watch("restore", 30)
        print("   -> %s" % ("жив" if ok2 else "ЗАВИС"), flush=True)
        c2 = cpu_of(tid, 6) if ok2 else 0.0
        print("   CPU после возврата: %.3f s/s" % c2, flush=True)
        return 0

    print("\nВЕРДИКТ: p.bTickPhysicsAsync вешает сервер — не применять", flush=True)
    return 3


if __name__ == "__main__":
    sys.exit(main())

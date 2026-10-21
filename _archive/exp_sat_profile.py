# -*- coding: utf-8 -*-
"""
Профиль GameThread при снятом лимите тиков и со всеми кэшами включёнными.

Это то, что реально осталось на GameThread, когда он работает на полную.

    python exp_sat_profile.py [--limit 200000] [--seconds 120]
"""
import argparse
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


def alive():
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=200000)
    ap.add_argument("--seconds", type=int, default=120)
    args = ap.parse_args()

    if not wait_ready():
        print("не готов")
        return 1
    tid = game_tid()
    print("game thread tid=%d" % tid, flush=True)

    print("\n[1] все кэши включены", flush=True)
    for c in ("TickProf.fncache 1", "TickProf.iscache 1", "TickProf.cachename 1"):
        cmd(c)
        time.sleep(3)
    cmd("TickProf.overlaptrim 2")
    time.sleep(10)

    print("[2] лимит тиков %d" % args.limit, flush=True)
    cmd("TickProf.maxfps %d" % args.limit)
    time.sleep(5)
    for ln in log_tail(10):
        if "maxfps" in ln or "cache" in ln:
            print("   " + ln.split(" ", 1)[-1])

    print("[3] прогрев 30 с", flush=True)
    time.sleep(30)
    print("   cpu %.3f s/s" % cpu_of(tid, 5), flush=True)

    print("[4] профиль %d с" % args.seconds, flush=True)
    cmd("TickProf.start %d" % args.seconds)
    time.sleep(args.seconds + 15)
    print("   cpu во время профиля %.3f s/s" % cpu_of(tid, 5), flush=True)

    files = sorted((f for f in os.listdir(PDIR) if f.endswith(".bin")),
                   key=lambda f: os.path.getmtime(os.path.join(PDIR, f)))
    if files:
        print("\nпрофиль: %s" % files[-1])
        for f in files[-1:]:
            print("   %s (%d байт)" % (f, os.path.getsize(os.path.join(PDIR, f))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
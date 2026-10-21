# -*- coding: utf-8 -*-
"""
Цикл 6: кэш IsChildOf + проверка, что правки складываются.

    python exp_cycle6.py
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
        return rcon.rcon(text, timeout=10) if False else rcon.rcon(text, timeout=timeout)
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
    print("   %-26s cpu %.3f->%.3f s/s | тиков/с %.1f" % (label, c0, c1, tps), flush=True)
    return {"cpu": (c0 + c1) / 2.0, "tps": tps, "alive": c1 > 0.005}


def show(keys, n=80):
    for ln in log_tail(n):
        if any(k in ln for k in keys):
            print("      " + ln.split(" ", 1)[-1])


def main():
    if not wait_ready():
        print("не готов")
        return 1
    tid = game_tid()
    print("game thread tid=%d" % tid, flush=True)
    res = {}

    print("\n[0] чистое состояние (без наших правок)", flush=True)
    cmd("TickProf.cachename 0")
    cmd("TickProf.fncache 0")
    cmd("TickProf.iscache 0")
    time.sleep(6)
    show(("canvas", "fncache", "iscache"))
    res["raw"] = measure("RAW", tid, 40)

    print("\n[1] + кэш FindFunctionByName", flush=True)
    cmd("TickProf.fncache 1")
    time.sleep(5)
    show(("fncache",))
    res["fn"] = measure("+FNCACHE", tid, 35)
    if res["fn"] and not res["fn"]["alive"]:
        return 2

    print("\n[2] + кэш IsChildOf", flush=True)
    cmd("TickProf.iscache 1")
    time.sleep(5)
    show(("iscache",))
    res["is"] = measure("+ISCACHE", tid, 35)
    if res["is"] and not res["is"]["alive"]:
        return 3

    print("\n[3] + кэш канвасов", flush=True)
    cmd("TickProf.cachename 1")
    time.sleep(5)
    show(("canvas",))
    res["canvas"] = measure("+CANVAS", tid, 35)
    if res["canvas"] and not res["canvas"]["alive"]:
        return 4

    print("\n[4] + обрезка пересечений порог 2", flush=True)
    cmd("TickProf.overlaptrim 2")
    time.sleep(12)
    show(("overlaptrim",))
    res["trim2"] = measure("+TRIM2", tid, 35)
    if res["trim2"] and not res["trim2"]["alive"]:
        return 5

    print("\n[5] census того, что осталось", flush=True)
    cmd("TickProf.overlapsizes")
    time.sleep(12)
    show(("overlapsizes",))

    print("\n[итог]", flush=True)
    prev = None
    for k in ("raw", "fn", "is", "canvas", "trim2"):
        r = res.get(k)
        if not r:
            continue
        delta = ""
        if prev:
            delta = "  (%+.1f%%)" % (100.0 * (r["cpu"] - prev) / prev if prev else 0.0)
        print("   %-8s cpu=%.3f s/s  тиков/с=%.1f%s" % (k, r["cpu"], r["tps"], delta))
        prev = r["cpu"]
    if res.get("raw", {}).get("cpu"):
        b = res["raw"]["cpu"]
        for k in ("fn", "is", "canvas", "trim2"):
            if res.get(k):
                print("   суммарно %-8s −%.0f%%" % (k, 100.0 * (b - res[k]["cpu"]) / b))
    return 0


if __name__ == "__main__":
    sys.exit(main())

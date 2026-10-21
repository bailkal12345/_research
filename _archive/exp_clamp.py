# -*- coding: utf-8 -*-
"""
Проверка зажима тикрейта: 120 или CPU?

UGameEngine::GetMaxTickRate зажимает NetServerMaxTickRate в [10, 120]
(константа 0x78 в MOV ECX,0x78). Наблюдаемый потолок 114–117 т/с подозрительно
близок к 120. Поднимаем границу патчем и смотрим, уедет ли потолок.

Если уедет — стена была в зажиме, и тогда все наши оптимизации CPU начинают
конвертироваться в пропускную способность. Если нет — стена настоящая.

    python exp_clamp.py
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


def measure(label, tid, seconds=30):
    c = cpu_of(tid, 4)
    cmd("TickProf.perf %d" % seconds)
    time.sleep(seconds + 5)
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
    print("   %-28s тиков/с %7.1f | cpu %.3f s/s | %.2f мс/тик"
          % (label, tps, c, 1000.0 * c / tps if tps else 0), flush=True)
    return {"tps": tps, "cpu": c, "alive": c > 0.005}


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

    print("\n[1] штатный лимит 30", flush=True)
    cmd("TickProf.maxfps 0")
    time.sleep(5)
    measure("лимит 30", tid, 25)

    print("\n[2] лимит 200000, зажим НЕ тронут", flush=True)
    cmd("TickProf.maxfps 200000")
    time.sleep(6)
    show(("maxfps",))
    a = measure("200000, зажим 120", tid, 30)
    if not a["alive"]:
        return 2

    print("\n[3] поднимаем зажим 120 -> 100000", flush=True)
    cmd("TickProf.fixclamp 1")
    time.sleep(6)
    show(("tickclamp",))
    b = measure("200000, зажим снят", tid, 30)
    if not b["alive"]:
        print("   сервер не выжил — возвращаем зажим")
        cmd("TickProf.fixclamp 0")
        return 3

    print("\n[4] то же + оптимизации (кэши и обрезка)", flush=True)
    for c in ("TickProf.fncache 1", "TickProf.iscache 1", "TickProf.cachename 1", "TickProf.nochart 1"):
        cmd(c)
        time.sleep(3)
    cmd("TickProf.overlaptrim 2")
    time.sleep(15)
    d = measure("200000, зажим снят + кэши", tid, 30)

    print("\n[5] возврат", flush=True)
    cmd("TickProf.fixclamp 0")
    time.sleep(5)
    cmd("TickProf.maxfps 0")
    time.sleep(6)
    show(("tickclamp", "maxfps"))
    measure("возврат к штатному", tid, 20)

    print("\n[итог]", flush=True)
    for label, r in (("200000, зажим 120", a), ("200000, зажим снят", b),
                     ("+ оптимизации", d)):
        if r:
            print("   %-22s %7.1f т/с" % (label, r["tps"]))
    if a["tps"] and b["tps"]:
        print("   подъём от снятия зажима: %+.0f%%" % (100.0 * (b["tps"] - a["tps"]) / a["tps"]))
    print("   сервер жив:", alive())
    return 0


if __name__ == "__main__":
    sys.exit(main())
# -*- coding: utf-8 -*-
"""
Тесты с подключённым игроком.

С игроком GameThread загружен в 6 раз сильнее (3.34 s/s против 0.53 на пустом),
и профиль другой: на первом месте поиск функций по имени (его снимает кэш),
заметная доля ИИ динозавров (её сокращает отсечение по расстоянию).

Осторожность: без выгрузки плагина, без полного отключения пересечений,
без асинхронных тиков — это всё уже было проверено как опасное.

    python exp_player.py
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
    ms_tick = 1000.0 * c1 / tps if tps else 0.0
    print("   %-30s тиков/с %5.1f | cpu %.3f s/s | %.2f мс CPU на тик"
          % (label, tps, c1, ms_tick), flush=True)
    return {"tps": tps, "cpu": c1, "ms_tick": ms_tick, "alive": c1 > 0.005}


def show(keys, n=60):
    for ln in log_tail(n):
        if any(k in ln for k in keys):
            print("      " + ln.split(" ", 1)[-1])


def main():
    tid = game_tid()
    if not tid:
        print("нет game thread")
        return 1
    print("game thread tid=%d" % tid, flush=True)
    if not alive():
        print("RCON не отвечает")
        return 1

    print("\n[0] состояние сервера на старте", flush=True)
    print("   RCON живой, кэши выключены?", flush=True)
    for c in ("TickProf.fncache 0", "TickProf.iscache 0", "TickProf.cachename 0"):
        cmd(c)
    time.sleep(4)
    base = measure("БЕЗ ОПТИМИЗАЦИЙ", tid, 30)

    print("\n[1] кэши (кэш FindFunctionByName снимает первый пункт профиля)", flush=True)
    for c in ("TickProf.fncache 1", "TickProf.iscache 1", "TickProf.cachename 1"):
        cmd(c)
        time.sleep(3)
    show(("fncache", "iscache", "canvas"))
    cached = measure("С КЭШАМИ", tid, 30)
    if not cached["alive"]:
        return 2

    print("\n[2] обрезка пересечений", flush=True)
    cmd("TickProf.overlaptrim 2")
    time.sleep(15)
    show(("overlaptrim",))
    trim = measure("+ ОБРЕЗКА ПЕРЕСЕЧЕНИЙ", tid, 30)
    if not trim["alive"]:
        return 3

    print("\n[3] отсечение тиков по расстоянию: сначала безопасный большой радиус", flush=True)
    cmd("TickProf.cull 50000")
    time.sleep(8)
    show(("cull",))
    r1 = measure("CULЛ 50 км (эффекта нет)", tid, 30)
    if not r1["alive"]:
        return 4

    print("\n[4] радиус 15 км", flush=True)
    cmd("TickProf.cull 15000")
    time.sleep(10)
    show(("cull",))
    r2 = measure("CULЛ 15 км", tid, 30)
    cmd("TickProf.cullstat")
    time.sleep(4)
    show(("cull:",))
    if not alive():
        print("   сервер перестал отвечать — откатываем")
        cmd("TickProf.cull 0")
        return 5

    print("\n[5] радиус 8 км", flush=True)
    cmd("TickProf.cull 8000")
    time.sleep(10)
    show(("cull",))
    r3 = measure("CULЛ 8 км", tid, 30)
    cmd("TickProf.cullstat")
    time.sleep(4)
    show(("cull:",))
    if not alive():
        print("   сервер перестал отвечать — откатываем")
        cmd("TickProf.cull 0")
        return 6

    print("\n[6] возврат отсечения", flush=True)
    cmd("TickProf.cull 0")
    time.sleep(8)
    back = measure("БЕЗ ОТСЕЧЕНИЯ", tid, 30)

    print("\n[итог]", flush=True)
    rows = [("база", base), ("кэши", cached), ("+обрезка", trim),
            ("cull 50км", r1), ("cull 15км", r2), ("cull 8км", r3), ("возврат", back)]
    ref = base["ms_tick"] if base else 0.0
    for label, r in rows:
        if not r:
            continue
        d = ("  %+.0f%%" % (100.0 * (r["ms_tick"] - ref) / ref)) if ref else ""
        print("   %-14s cpu %.3f s/s | %.2f мс/тик%s" % (label, r["cpu"], r["ms_tick"], d))
    return 0


if __name__ == "__main__":
    sys.exit(main())
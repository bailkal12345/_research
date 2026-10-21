# -*- coding: utf-8 -*-
"""
П8: контрольный A/B патча зажима тикрейта в УСТАНОВИВШЕМСЯ режиме.

Претензия к прошлому замеру справедлива: окна шли подряд на затухающей после
старта нагрузке, поэтому скачок 32 → 65 неотделим от остывания стриминга.
Здесь наоборот: ждём 10 минут после старта мира, прогреваем, и только потом
чередуем окна A/B/A/B. Критерий — устойчивое превышение 120 т/с.

Плюс свип значения лимита, чтобы понять, где встанет настоящий потолок.

    python exp_clamp_ab.py [--settle 600] [--window 30]
"""
import argparse
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
    print("   %-30s %7.1f т/с | cpu %.3f s/s | %.2f мс/тик | загрузка %.0f%%"
          % (label, tps, c, 1000.0 * c / tps if tps else 0, 100.0 * c),
          flush=True)
    return {"tps": tps, "cpu": c, "alive": c > 0.005}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--settle", type=int, default=600, help="секунд ожидания устойчивого режима")
    ap.add_argument("--window", type=int, default=30)
    args = ap.parse_args()

    if not wait_ready():
        print("не готов")
        return 1
    tid = game_tid()
    print("game thread tid=%d" % tid, flush=True)

    print("\n[0] оптимизации включены, зажим пока штатный", flush=True)
    for c in ("TickProf.fncache 1", "TickProf.iscache 1", "TickProf.cachename 1", "TickProf.nochart 1"):
        cmd(c)
        time.sleep(3)
    cmd("TickProf.overlaptrim 2")
    time.sleep(15)

    print("\n[1] лимит 200000, зажим штатный", flush=True)
    cmd("TickProf.fixclamp 0")
    cmd("TickProf.maxfps 200000")
    time.sleep(6)
    for ln in log_tail(20):
        if "tickclamp" in ln or "maxfps" in ln:
            print("   " + ln.split(" ", 1)[-1])

    print("\n[2] устаканивание %d с (стриминг должен остыть)" % args.settle, flush=True)
    t0 = time.time()
    while time.time() - t0 < args.settle:
        time.sleep(30)
        c = cpu_of(tid, 4)
        print("   прошло %4d с, cpu %.3f s/s" % (int(time.time() - t0), c), flush=True)

    print("\n[3] прогрев 60 с", flush=True)
    measure("прогрев", tid, 60)

    print("\n[4] чередование окон A/B/A/B (окно %d с)" % args.window, flush=True)
    res = []
    for rep in range(2):
        cmd("TickProf.fixclamp 0")
        time.sleep(5)
        a = measure("A%d зажим 120" % rep, tid, args.window)
        cmd("TickProf.fixclamp 1")
        time.sleep(5)
        b = measure("B%d зажим снят" % rep, tid, args.window)
        res += [("A%d" % rep, a), ("B%d" % rep, b)]
        if not alive():
            print("   сервер не отвечает")
            break

    print("\n[5] свип лимита при снятом зажиме", flush=True)
    cmd("TickProf.fixclamp 1")
    time.sleep(4)
    for lim in (150, 200, 400):
        cmd("TickProf.maxfps %d" % lim)
        time.sleep(6)
        measure("лимит %d" % lim, tid, args.window)

    print("\n[итог]", flush=True)
    print("   %-24s %10s %12s" % ("окно", "т/с", "мс/тик"))
    for label, r in res:
        if r:
            print("   %-24s %10.1f %12.2f" % (label, r["tps"], 1000.0 * r["cpu"] / r["tps"] if r["tps"] else 0))
    aa = [r["tps"] for l, r in res if l.startswith("A") and r]
    bb = [r["tps"] for l, r in res if l.startswith("B") and r]
    if aa and bb:
        print("\n   среднее A (зажим 120)   %.1f т/с" % (sum(aa) / len(aa)))
        print("   среднее B (зажим снят)  %.1f т/с" % (sum(bb) / len(bb)))
        print("   устойчивое превышение 120: %s" % ("ДА" if max(bb) > 120 else "НЕТ"))
    print("\n   сервер жив:", alive())
    return 0


if __name__ == "__main__":
    sys.exit(main())
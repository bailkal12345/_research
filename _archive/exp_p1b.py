# -*- coding: utf-8 -*-
"""
П1-дубль-три: StartFrame реагирует на число задач линейно или нет?

П1 уже показал: в очередь ставится 223 задачи на кадр, а не ~52 780.
Значит 2.7 мс / 223 = 12.3 мкс на задачу — абсурд для постановки в очередь.
Дискриминатор: гасим тики у акторов-динозавров (это основная масса из 223)
и смотрим, падает ли StartFrame пропорционально.

  * упал пропорционально  -> стоимость на задачу, П2 имеет смысл;
  * почти не упал          -> стоимость на уровень/на кадр, П2 бессмысленна.

Без снятия лимита тиков: в прошлый раз сервер на этом завис.

    python exp_p1b.py
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


def log_tail(n=120):
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


def newest_csv():
    files = sorted((f for f in os.listdir(PDIR) if f.endswith(".csv")),
                   key=lambda f: os.path.getmtime(os.path.join(PDIR, f)))
    return files[-1] if files else None


def probe(label, tid, seconds=30):
    before = newest_csv()
    cmd("TickProf.tickq %d" % (seconds - 6))
    time.sleep(2)
    cmd("TickProf.start %d" % seconds)
    time.sleep(seconds + 14)
    c = cpu_of(tid, 3)
    cmd("TickProf.tickqreport")
    time.sleep(4)
    q = ""
    for ln in reversed(log_tail(40)):
        if "задач" in ln and "tickq" in ln:
            q = ln.split("tickq:")[-1].strip()
            break
    after = newest_csv()
    sf_ms, frames = 0.0, 0
    if after and after != before:
        with open(os.path.join(PDIR, after), encoding="utf-8", errors="replace") as f:
            for ln in f:
                p = ln.split(",")
                if p[0] == "FTickTaskManager.StartFrame" and len(p) == 5:
                    sf_ms, frames = float(p[2]), 0
                if p[0] == "frames" and len(p) == 2:
                    frames = int(p[1])
    per_frame = sf_ms / frames if frames else 0.0
    print("   %-24s задач/кадр: %-46s StartFrame %.3f мс/кадр | cpu %.3f"
          % (label, q or "?", per_frame, c), flush=True)
    return {"q": q, "ms": per_frame, "cpu": c, "frames": frames}


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

    for h in range(0, 5):
        cmd("TickProf.hook %d" % h)
    time.sleep(8)

    print("\n[1] перепись тикающих акторов (сколько их из 223)", flush=True)
    cmd("TickProf.actortickoff -")  # пусто не сработает, просто пропуск
    time.sleep(2)

    print("\n[2] база", flush=True)
    base = probe("база", tid, 30)

    print("\n[3] гасим тики у динозавров", flush=True)
    cmd("TickProf.actortickoff Dino")
    time.sleep(12)
    show(("actortickoff",))
    off = probe("без тиков Dino", tid, 30)

    print("\n[4] гасим вообще все тики акторов (PrimalCharacter)", flush=True)
    cmd("TickProf.actortickoff PrimalCharacter")
    time.sleep(12)
    show(("actortickoff",))
    off2 = probe("без PrimalCharacter", tid, 30)

    print("\n[вердикт П1-дубль-три]", flush=True)
    if base["ms"] and off["ms"]:
        d = 100.0 * (base["ms"] - off["ms"]) / base["ms"]
        print("   StartFrame: %.3f -> %.3f мс/кадр (−%.0f%%)" % (base["ms"], off["ms"], d))
        if d > 40:
            print("   → стоимость на задачу: П2 имеет смысл")
        else:
            print("   → стоимость НЕ на задачу: П2 бессмысленна, смотреть на уровни")
    print("   сервер жив:", alive())
    return 0


if __name__ == "__main__":
    sys.exit(main())
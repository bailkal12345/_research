# -*- coding: utf-8 -*-
"""
П1: решающий тест — сколько тик-задач ставится в очередь за кадр.

Гипотеза брифа: StartFrame (~3.8 мс) стоит не 700 задач по 5.4 мкс, а ~52 780
задач по 72 нс. Проверяем прямым счётчиком вызовов FTickFunction::QueueTickFunction,
затем смотрим, как StartFrame реагирует на отключение тиков у акторов.

    python exp_p1.py
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


def last_phases():
    """Читаем последний CSV с фазовыми таймерами."""
    pdir = r"C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi\Plugins\TickProf"
    files = sorted((f for f in os.listdir(pdir) if f.endswith(".csv")), key=lambda f: os.path.getmtime(os.path.join(pdir, f)))
    if not files:
        return {}
    out = {}
    with open(os.path.join(pdir, files[-1]), encoding="utf-8", errors="replace") as f:
        rows = f.read().splitlines()
    frames = 0
    for ln in rows:
        parts = ln.split(",")
        if len(parts) == 5 and parts[0] != "phase":
            try:
                out[parts[0]] = {"calls": int(parts[1]), "total_ms": float(parts[2]),
                                 "avg_us": float(parts[3]), "max_ms": float(parts[4])}
            except ValueError:
                pass
        elif parts[0] == "frames":
            frames = int(parts[1])
    out["_frames"] = frames
    out["_file"] = files[-1]
    return out


def phase_probe(label, tid, seconds=30):
    """Замер: фазовые таймеры + счётчик задач + CPU."""
    cmd("TickProf.tickq %d" % (seconds - 6))
    time.sleep(2)
    cmd("TickProf.start %d" % seconds)
    time.sleep(seconds + 12)
    c = cpu_of(tid, 3)
    cmd("TickProf.tickqreport")
    time.sleep(4)
    ph = last_phases()
    q = ""
    for ln in reversed(log_tail(40)):
        if "tickq:" in ln and "задач" in ln:
            q = ln.split("tickq:")[-1].strip()
            break
    sf = ph.get("FTickTaskManager.StartFrame", {})
    frames = ph.get("_frames", 0) or 1
    ms_frame = sf.get("total_ms", 0.0) / 1000.0
    print("   %-26s задач/кадр: %s" % (label, q or "нет данных"), flush=True)
    print("   %-26s StartFrame %.0f мс за %d кадров = %.3f мс/кадр | cpu %.3f s/s"
          % ("", sf.get("total_ms", 0), frames, ms_frame, c), flush=True)
    return {"q": q, "ms_frame": ms_frame, "cpu": c, "ph": ph}


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

    # фазовые таймеры
    for h in range(0, 5):
        cmd("TickProf.hook %d" % h)
    time.sleep(8)

    print("\n[1] сколько задач в очереди на кадр ( штатный тикрейт )", flush=True)
    base = phase_probe("база", tid, 30)

    print("\n[2] то же при снятом лимите тиков", flush=True)
    cmd("TickProf.maxfps 200000")
    time.sleep(6)
    sat = phase_probe("насыщение", tid, 30)

    print("\n[3] возвращаем штатный лимит", flush=True)
    cmd("TickProf.maxfps 0")
    time.sleep(5)

    print("\n[4] П1-дубль-три: гасим тики у акторов и смотрим StartFrame", flush=True)
    cmd("TickProf.actortickoff Dino")
    time.sleep(10)
    show(("actortickoff",))
    trim = phase_probe("без тиков Dino", tid, 30)

    print("\n[итог П1]", flush=True)
    print("   база:       %s задач/кадр, StartFrame %.3f мс/кадр" % (base["q"], base["ms_frame"]))
    print("   насыщение:  %s задач/кадр, StartFrame %.3f мс/кадр" % (sat["q"], sat["ms_frame"]))
    print("   без Dino:   %s задач/кадр, StartFrame %.3f мс/кадр" % (trim["q"], trim["ms_frame"]))
    print("   сервер жив:", alive())
    return 0


if __name__ == "__main__":
    sys.exit(main())
# -*- coding: utf-8 -*-
"""
Тест-леджер: одно окно, одновременно CPU потока, фазовые таймеры и сэмплер.

Заявленное противоречие: сумма фаз (StartFrame + RunTickGroup) больше полного
CPU на тик. Либо окна разные, либо фазовый таймер измеряет не то.

Здесь всё снимается в одном окне длиной N секунд:
  (a) внешний CPU потока GameThread — накоплением отсчётов раз в секунду;
  (b) фазовые таймеры — из CSV того же профиля;
  (с) сэмплер — из того же .bin, доля простоя отдельно.

Плюс перепись размеров тик-множеств по уровням (судьба гипотезы скана).

    python exp_ledger.py [--window 45]
"""
import argparse
import os
import struct
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


def newest(ext):
    files = sorted((f for f in os.listdir(PDIR) if f.endswith(ext)),
                   key=lambda f: os.path.getmtime(os.path.join(PDIR, f)))
    return files[-1] if files else None


def read_csv(name):
    out = {}
    frames = 0
    with open(os.path.join(PDIR, name), encoding="utf-8", errors="replace") as f:
        for ln in f:
            p = ln.split(",")
            if len(p) == 5 and p[0] != "phase":
                try:
                    out[p[0]] = float(p[2])
                except ValueError:
                    pass
            elif p[0] == "frames" and len(p) == 2:
                frames = int(p[1])
    out["_frames"] = frames
    return out


def read_bin(name):
    with open(os.path.join(PDIR, name), "rb") as f:
        base, count = struct.unpack("<QQ", f.read(16))
        f.read(8 * count)
    return count


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", type=int, default=45)
    args = ap.parse_args()

    if not wait_ready():
        print("не готов")
        return 1
    tid = game_tid()
    print("game thread tid=%d" % tid, flush=True)

    print("\n[1] перепись тик-множеств по уровням", flush=True)
    cmd("TickProf.ticksets")
    time.sleep(6)
    for ln in log_tail(20):
        if "ticksets:" in ln:
            print("   " + ln.split(" ", 1)[-1])

    print("\n[2] фазовые хуки (включая разбиение StartFrame)", flush=True)
    for h in range(0, 5):
        cmd("TickProf.hook %d" % h)
    time.sleep(10)
    for ln in log_tail(30):
        if "hook " in ln and ("FillLevelList" in ln or "QueueAllTicks" in ln or "QueueNewly" in ln):
            print("   " + ln.split(" ", 1)[-1])

    print("\n[3] окно %d с: одновременно CPU, фазы, сэмплер" % args.window, flush=True)
    before_bin, before_csv = newest(".bin"), newest(".csv")
    v0 = threadcpu.cpu_times(tid)
    cmd("TickProf.start %d" % args.window)
    t0 = time.time()
    vals = []
    while time.time() - t0 < args.window:
        time.sleep(2.0)
        v = threadcpu.cpu_times(tid)
        if v is not None and v0 is not None:
            vals.append(v)
    v1 = threadcpu.cpu_times(tid)
    time.sleep(14)

    cpu_s = (v1 - v0) if (v1 is not None and v0 is not None) else 0.0
    win = args.window
    bin_f, csv_f = newest(".bin"), newest(".csv")
    if not bin_f or bin_f == before_bin:
        print("   профиль не записан")
        return 2
    samples = read_bin(bin_f)
    ph = read_csv(csv_f)
    frames = ph.get("_frames", 0)

    print("\n=== ЛЕДЖЕР ===", flush=True)
    print("   окно                 %d с" % win)
    print("   кадров               %d  (%.1f т/с)" % (frames, frames / win))
    print("   сэмплов              %d  (%.0f в секунду)" % (samples, samples / win))
    print("   CPU GameThread       %.2f с  (%.0f%% окна)" % (cpu_s, 100.0 * cpu_s / win))
    print("   CPU на кадр          %.3f мс" % (1000.0 * cpu_s / frames if frames else 0))
    print()
    total = 0.0
    for k in sorted(ph):
        if k.startswith("_"):
            continue
        ms = ph[k]
        total += ms
        print("   фаза %-34s %9.1f мс   %.2f мс/кадр" % (k, ms, ms / frames if frames else 0))
    print("   %-40s %9.1f мс   %.2f мс/кадр" % ("СУММА ФАЗ", total, total / frames if frames else 0))
    print()
    if frames:
        ratio = (total / 1000.0) / cpu_s if cpu_s else 0
        print("   сумма фаз / CPU      %.2f" % ratio)
        print("   вердикт: %s" % ("таймеры сходятся с CPU" if 0.9 <= ratio <= 1.15 else
                                 "таймеры НЕ сходятся с CPU — измеряют не то"))
    sf = [f for f in os.listdir(PDIR) if f.endswith(".sfstack")]
    if sf:
        newest_sf = max(sf, key=lambda f: os.path.getmtime(os.path.join(PDIR, f)))
        print("\n   стеки StartFrame: %s" % newest_sf)
    for ln in log_tail(20):
        if "StartFrame:" in ln and "стек-сэмплов" in ln:
            print("   " + ln.split(" ", 1)[-1])

    print("\n[4] cachestat в устоявшемся режиме", flush=True)
    cmd("TickProf.cachestat")
    time.sleep(5)
    for ln in log_tail(20):
        if "cachestat:" in ln:
            print("   " + ln.split(" ", 1)[-1])
    print("\nсервер жив:", alive())
    return 0


if __name__ == "__main__":
    sys.exit(main())
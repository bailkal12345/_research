# -*- coding: utf-8 -*-
"""
Автопрогон измерений GameThread на живом сервере ARK.

    python run_measure.py [--sample-seconds 120] [--plugin-dir ...]

Последовательность:
  1. ждём готовности мира и RCON;
  2. грузим плагин TickProf;
  3. ставим хуки по одному, после каждого проверяем, что GameThread жив
     (по CPU потока и по тому, что RCON отвечает) — так ловится хук, который ломает тик;
  4. включаем сэмплирование на N секунд;
  5. останавливаем и оставляем файлы в каталоге плагина.
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import rcon  # noqa: E402
import threadcpu  # noqa: E402

PLUGIN_DIR = r"C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi\Plugins\TickProf"

# Порядок важен: сначала безопасные хуки внутри тика мира, потом внешние обвязки.
# FEngineLoop.Tick (0) при проверке ронял сервер — идёт последним и только по --risky.
HOOKS = [
    (3, "UWorld.RunTickGroup"),
    (4, "FTickTaskManager.StartFrame"),
    (5, "FTickTaskManager.EndFrame"),
    (6, "UNetDriver.TickDispatch"),
    (7, "Global.CollectGarbage"),
    (8, "AShooterGameMode.Tick"),
    (9, "AShooterGameState.Tick"),
    (10, "UNetDriver.TickFlush"),
    (11, "UWorld.TickNetClient"),
    (1, "UEngine.Tick"),
    # (2, "UWorld.Tick") — на нём уже висит хук ArkApi (CheckOnTickCallbacks);
    # второй хук в цепочке роняет сервер, проверено.
]
RISKY = [(0, "FEngineLoop.Tick")]


def cmd(text, timeout=8):
    try:
        return rcon.rcon(text, timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        return "<%s>" % type(exc).__name__


def wait_ready(minutes=12):
    deadline = time.time() + minutes * 60
    while time.time() < deadline:
        pids = threadcpu.find_pid()
        if pids:
            try:
                out = rcon.rcon("plugins.list", timeout=4)
                if "no response" in out or out:
                    print("[wait] server ready, pid=%d" % pids[0], flush=True)
                    return pids[0]
            except Exception:
                pass
        time.sleep(10)
    raise SystemExit("server did not become ready")


def game_tid(wait_seconds=900):
    """GameThread узнаём из лога плагина, но ждём первый тик: до InitWorld тиков нет."""
    log = os.path.join(PLUGIN_DIR, "TickProf.log")
    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        try:
            with open(log, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    if "game thread tid=" in line:
                        return int(line.strip().split("tid=")[-1])
        except OSError:
            pass
        time.sleep(5)
    return 0


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


def alive(tid, baseline):
    """Поток жив и что-то делает?"""
    c = cpu_of(tid)
    return c, c > baseline * 0.2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample-seconds", type=float, default=120.0)
    ap.add_argument("--risky", action="store_true", help="в конце проверить и FEngineLoop.Tick")
    args = ap.parse_args()

    pid = wait_ready()
    print("[step] loading plugin", flush=True)
    print(cmd("plugins.load TickProf"), flush=True)
    time.sleep(4)

    tid = game_tid()
    print("[step] game thread tid=%d" % tid, flush=True)
    if not tid:
        raise SystemExit("plugin did not report game thread")

    base = cpu_of(tid, 6)
    print("[baseline] GameThread cpu=%.3f s/s (%.1f%% of a core)" % (base, base * 100), flush=True)

    # ---- фаза 1: чистое сэмплирование, без единого патча ----
    print("[step] phase 1: sampling WITHOUT hooks for %.0f s" % args.sample_seconds, flush=True)
    print("  start: %s" % cmd("TickProf.start"), flush=True)
    t_end = time.time() + args.sample_seconds
    while time.time() < t_end:
        time.sleep(5)
    print("  stop: %s" % cmd("TickProf.stop"), flush=True)
    time.sleep(3)
    print("  status: %s" % cmd("TickProf.status"), flush=True)

    # ---- фаза 2: фазовые таймеры через хуки ----
    print("[step] phase 2: installing hooks one by one", flush=True)
    for idx, name in HOOKS:
        print("  -> hook %-2d %s" % (idx, name), flush=True)
        print("     rcon: %s" % cmd("TickProf.hook %d" % idx), flush=True)
        time.sleep(4)
        c, ok = alive(tid, base)
        print("     game thread cpu=%.3f s/s -> %s" % (c, "ok" if ok else "DEAD?"), flush=True)
        if not ok:
            print("[abort] hook %d (%s) killed the tick; stopping" % (idx, name), flush=True)
            break

    if args.risky:
        print("[step] risky hooks", flush=True)
        for idx, name in RISKY:
            print("  -> hook %-2d %s" % (idx, name), flush=True)
            print("     rcon: %s" % cmd("TickProf.hook %d" % idx), flush=True)
            time.sleep(4)
            c, ok = alive(tid, base)
            print("     game thread cpu=%.3f s/s -> %s" % (c, "ok" if ok else "DEAD?"), flush=True)
            if not ok:
                break

    print("[step] sampling with hooks for %.0f s" % args.sample_seconds, flush=True)
    print("  start: %s" % cmd("TickProf.start"), flush=True)
    t_end = time.time() + args.sample_seconds
    while time.time() < t_end:
        time.sleep(5)
    print("  stop: %s" % cmd("TickProf.stop"), flush=True)
    time.sleep(3)

    for _ in range(30):
        if any(f.startswith("prof_") for f in os.listdir(PLUGIN_DIR)):
            break
        time.sleep(2)

    for f in sorted(os.listdir(PLUGIN_DIR)):
        if f.startswith("prof_"):
            print("  artifact: %s" % os.path.join(PLUGIN_DIR, f), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
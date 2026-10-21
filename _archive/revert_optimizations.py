# -*- coding: utf-8 -*-
"""
Ключ отката оптимизаций вахты (Агент-3, doit.txt §6).

    python revert_optimizations.py            # откатить все применённые правки
    python revert_optimizations.py --list     # показать, что будет откачено

Откат полностью обратим на стороне плагина: кэши выключаются, зажим
возвращается к штатным 120, лимит тиков — к штатному значению.
Снятые bGenerateOverlapEvents и выключенные тики НЕ восстанавливаются
без перезапуска сервера — это указано в выводе.
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("RCON_HOST", "192.168.8.218")
sys.path.insert(0, HERE)

import rcon  # noqa: E402

REVERT = [
    ("TickProf.fncache 0", "кэш UClass::FindFunctionByName"),
    ("TickProf.iscache 0", "кэш UStruct::IsChildOf"),
    ("TickProf.cachename 0", "кэш DoGetCanvasByName"),
    ("TickProf.nochart 0", "ведение графиков FPS"),
    ("TickProf.fixclamp 0", "поднятый зажим тикрейта"),
    ("TickProf.maxfps 0", "NetServerMaxTickRate -> штатное"),
    ("TickProf.tickflags 0", "разметка bRunOnAnyThread"),
]

# НЕ откатывается командами: требует перезапуска сервера
RESTART_ONLY = [
    "снятые overlaptrim 0/2/3 (bGenerateOverlapEvents + списки пересечений)",
    "выключенные тики TickProf.actortickoff (на вахте не применялись)",
]


def cmd(text, timeout=10):
    try:
        return rcon.rcon(text, timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        return "<%s>" % type(exc).__name__


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    print("Будет выполнено:")
    for c, d in REVERT:
        print("   %-24s %s" % (c, d))
    print("\nТребует переза��арска сервера (командами не откатывается):")
    for d in RESTART_ONLY:
        print("   -", d)

    if args.list:
        return 0

    for c, d in REVERT:
        print("   > %-24s -> %s" % (c, cmd(c)))
        time.sleep(3)
    print("\nОткат выполнен.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
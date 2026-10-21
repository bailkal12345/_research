# -*- coding: utf-8 -*-
"""
Применение проверенной конфигурации к запущенному серверу.

    python apply_recommended.py            # применить
    python apply_recommended.py --revert   # откатить (кроме overlaptrim)

Рекомендуемый набор (все правки измерены, ни одна не меняет семантику движка):

    TickProf.fncache 1        кэш UClass::FindFunctionByName
    TickProf.iscache 1        кэш UStruct::IsChildOf
    TickProf.cachename 1      кэш DoGetCanvasByName
    TickProf.overlaptrim 2    снятие раздутых списков пересечений

Чего применять нельзя:
    TickProf.fix concurrent 1 + TickProf.tickflags — асинхронные тики замедляют;
    TickProf.overlapall 1     — ломает игровые механики.
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import rcon  # noqa: E402

RECOMMENDED = [
    "TickProf.fncache 1",
    "TickProf.iscache 1",
    "TickProf.cachename 1",
    "TickProf.overlaptrim 2",
]

REVERT = [
    "TickProf.fncache 0",
    "TickProf.iscache 0",
    "TickProf.cachename 0",
]


def cmd(text, timeout=10):
    try:
        return rcon.rcon(text, timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        return "<%s>" % type(exc).__name__


def main():
    revert = "--revert" in sys.argv
    cmds = REVERT if revert else RECOMMENDED
    print("применяю: %s" % (", ".join(cmds) if not revert else "откат хуков"))
    for c in cmds:
        print("   > %-28s -> %s" % (c, cmd(c)))
        time.sleep(3)
    if not revert:
        print("   > %-28s -> %s" % ("TickProf.overlaptrim 2", cmd("TickProf.overlaptrim 2")))
    print("готово")
    return 0


if __name__ == "__main__":
    sys.exit(main())

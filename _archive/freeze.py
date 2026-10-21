# -*- coding: utf-8 -*-
"""
Детектор заморозки GameThread: процесс жив, но не тикает.

    python freeze.py [--pid N] [--probe 20]

Наблюдение: bench-запуск (deploy_map.py) тянет Steam-подсистему
(steam_api64.dll, steamclient64.dll, crashhandler64.dll). При отсутствии
сети/DNS SteamSocketsOpenSource пишет "gethostname failed ()", после чего
либо процесс доходит до тиков, либо Steam-крашхендлер снимает дамп и
сервер остаётся живым с 0.00 CPU во всех потоках — навсегда.

Модуль даёт быструю проверку «процесс жив, но ничего не делает», чтобы
не ждать RCON по полному таймауту.
"""
import argparse
import ctypes as C
from ctypes import wintypes as W

k32 = C.WinDLL("kernel32", use_last_error=True)


class FILETIME(C.Structure):
    _fields_ = [("dwLowDateTime", W.DWORD), ("dwHighDateTime", W.DWORD)]


k32.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
k32.OpenProcess.restype = W.HANDLE
k32.GetProcessTimes.argtypes = [W.HANDLE, C.POINTER(FILETIME), C.POINTER(FILETIME),
                                C.POINTER(FILETIME), C.POINTER(FILETIME)]
k32.CloseHandle.argtypes = [W.HANDLE]

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_ticks = W.FILETIME()


def cpu_total(pid):
    """Суммарное CPU процесса, с. None — процесс не открылся."""
    h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h or h == W.HANDLE(-1).value:
        return None
    try:
        c, e, k, u = FILETIME(), FILETIME(), FILETIME(), FILETIME()
        if not k32.GetProcessTimes(h, C.byref(e), C.byref(k), C.byref(u), C.byref(c)):
            return None
        v = (c.dwHighDateTime << 32) | c.dwLowDateTime
        return v / 1e7
    finally:
        k32.CloseHandle(h)


def busy(pid, probe=20.0):
    """Доля CPU процесса за окно probe секунд."""
    a = cpu_total(pid)
    if a is None:
        return None
    import time
    time.sleep(probe)
    b = cpu_total(pid)
    if b is None:
        return None
    return (b - a) / probe


def is_frozen(pid, probe=20.0, min_cpu=0.02):
    """True — процесс существует, но CPU ниже порога (заморозка)."""
    v = busy(pid, probe)
    return (v is not None and v < min_cpu), v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, default=0)
    ap.add_argument("--probe", type=float, default=20.0)
    a = ap.parse_args()
    pid = a.pid
    if not pid:
        import sys, os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import threadcpu
        p = threadcpu.find_pid()
        pid = (p[0] if isinstance(p, (list, tuple)) else p) if p else 0
    if not pid:
        print("процесс ShooterGameServer не найден")
        return 2
    fz, v = is_frozen(pid, a.probe)
    print("pid %d, доля CPU за %.0f с = %.3f -> %s"
          % (pid, a.probe, -1.0 if v is None else v,
             "ЗАМОРОЗКА" if fz else "работает"))
    return 1 if fz else 0


if __name__ == "__main__":
    C._handle = _ticks
    import sys
    sys.exit(main())
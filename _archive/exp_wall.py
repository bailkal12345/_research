# -*- coding: utf-8 -*-
"""
П3: из чего состоит «стена» — время вне измеренных фаз.

Снимает RIP потока GameThread много раз и группирует по верхней рамке.
Гипотеза брифа: это либо NtDelayExecution (ограничитель тикрейта), либо
NtWaitForSingleObject (ожидание воркеров/задачного графа).

    python exp_wall.py [--samples 200] [--interval 0.03]
"""
import argparse
import collections
import ctypes
import os
import sqlite3
import struct
import sys
import time
from ctypes import wintypes

sys.path.insert(0, r"C:\Dev\_research")
from symbolize import FuncTable  # noqa: E402

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

THREAD_SUSPEND_RESUME = 0x0002
THREAD_GET_CONTEXT = 0x0008
THREAD_QUERY_INFORMATION = 0x0040
CONTEXT_CONTROL = 0x00100000
MAXIMUM_SUPPORTED_CONTROL = 0x0010001F


class RIP(ctypes.Structure):
    _fields_ = [("Rip", ctypes.c_uint64), ("Rsp", ctypes.c_uint64), ("Eflags", ctypes.c_uint32)]


class FLOATING_SAVE_AREA(ctypes.Structure):
    _fields_ = [("ControlWord", ctypes.c_uint64), ("StatusWord", ctypes.c_uint64),
                ("TagWord", ctypes.c_uint64), ("ErrorOffset", ctypes.c_uint32),
                ("ErrorSelector", ctypes.c_uint32), ("DataOffset", ctypes.c_uint32),
                ("DataSelector", ctypes.c_uint32), ("MxCsr", ctypes.c_uint32),
                ("MxCsr_Mask", ctypes.c_uint32), ("FloatRegisters", ctypes.c_uint64 * 8),
                ("XmmRegisters", ctypes.c_uint64 * 32), ("Reserved3", ctypes.c_uint64 * 12)]


class CONTEXT(ctypes.Structure):
    _fields_ = [
        ("ContextFlags", ctypes.c_uint32), ("MxCsr", ctypes.c_uint32),
        ("SegCs", ctypes.c_uint16), ("SegDs", ctypes.c_uint16), ("SegEs", ctypes.c_uint16),
        ("SegFs", ctypes.c_uint16), ("SegGs", ctypes.c_uint16), ("SegSs", ctypes.c_uint16),
        ("EFlags", ctypes.c_uint32), ("Dr0", ctypes.c_uint64), ("Dr1", ctypes.c_uint64),
        ("Dr2", ctypes.c_uint64), ("Dr3", ctypes.c_uint64), ("Dr6", ctypes.c_uint64),
        ("Dr7", ctypes.c_uint64), ("FloatSave", FLOATING_SAVE_AREA),
        ("Rax", ctypes.c_uint64), ("Rcx", ctypes.c_uint64), ("Rdx", ctypes.c_uint64),
        ("Rbx", ctypes.c_uint64), ("Rsp", ctypes.c_uint64), ("Rbp", ctypes.c_uint64),
        ("Rsi", ctypes.c_uint64), ("Rdi", ctypes.c_uint64), ("R8", ctypes.c_uint64),
        ("R9", ctypes.c_uint64), ("R10", ctypes.c_uint64), ("R11", ctypes.c_uint64),
        ("R12", ctypes.c_uint64), ("R13", ctypes.c_uint64), ("R14", ctypes.c_uint64),
        ("R15", ctypes.c_uint64), ("Rip", ctypes.c_uint64),
    ]


LOG = r"C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi\Plugins\TickProf\TickProf.log"


def game_tid():
    try:
        with open(LOG, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        return 0
    for ln in reversed(lines):
        if "game thread tid=" in ln:
            return int(ln.strip().split("tid=")[-1])
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=200)
    ap.add_argument("--interval", type=float, default=0.03)
    args = ap.parse_args()

    tid = game_tid()
    if not tid:
        print("не найден game thread")
        return 1
    h = kernel32.OpenThread(THREAD_SUSPEND_RESUME | THREAD_GET_CONTEXT | THREAD_QUERY_INFORMATION, False, tid)
    if not h:
        print("OpenThread не удался")
        return 2

    con = sqlite3.connect(r"C:\Dev\_research\v361.sqlite")
    rows = con.execute("SELECT rva, name, size FROM fn WHERE tag=5 ORDER BY rva").fetchall()
    con.close()
    rvas = [r for r, n, s in rows]
    info = [(n, s if s > 0 else 0x40) for r, n, s in rows]

    import bisect

    def look(rva):
        i = bisect.bisect_right(rvas, rva) - 1
        if i >= 0 and rva < rvas[i] + info[i][1]:
            return info[i][0]
        return None

    base = ctypes.c_uint64()
    mbi = ctypes.create_string_buffer(4096)
    kernel32.GetModuleHandleW(None, ctypes.byref(base)) if False else None
    base = kernel32.GetModuleHandleW(None)
    image = ctypes.c_uint64(base)

    cnt = collections.Counter()
    retcnt = collections.Counter()
    for _ in range(args.samples):
        if kernel32.SuspendThread(h) == 0xFFFFFFFF:
            break
        ctx = CONTEXT()
        ctx.ContextFlags = CONTEXT_CONTROL
        ok = kernel32.GetThreadContext(h, ctypes.byref(ctx))
        kernel32.ResumeThread(h)
        if not ok:
            continue
        rva = ctx.Rip - image
        nm = look(rva)
        cnt[nm or ("внешний +0x%X" % (ctx.Rip - image if ctx.Rip > image else ctx.Rip))] += 1
        try:
            ret = ctypes.c_uint64.from_address(ctx.Rsp).value
            retnm = look(ret - image) if ret > image else None
            retcnt[retnm or ("<вне образа>")] += 1
        except Exception:
            retcnt["<не прочитать>"] += 1
        time.sleep(args.interval)
    kernel32.CloseHandle(h)

    print("сэмплов: %d, tid=%d\n" % (sum(cnt.values()), tid))
    print("=== верхняя рамка (где находится RIP) ===")
    for nm, c in cnt.most_common(14):
        print("   %5.1f%%  %s" % (100.0 * c / sum(cnt.values()), nm[:70]))
    print("\n=== что на [RSP] (адрес возврата) ===")
    for nm, c in retcnt.most_common(14):
        print("   %5.1f%%  %s" % (100.0 * c / sum(retcnt.values()), nm[:70]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
# -*- coding: utf-8 -*-
"""
Символизирует prof_*.bin (RIP-сэмплы GameThread) по таблице символов PDB.

    python symbolize.py <prof.bin> [--db v361.sqlite] [--top 40] [--pid 12345]

В .bin записано: u64 base образа, u64 count, затем count значений RIP.
Адреса вне образа игры относятся к внешним модулям; если передан --pid,
список модулей читается из живого процесса и адрес раскладывается как
"модуль+смещение" (там символов нет — только имена модулей).
"""
import argparse
import bisect
import os
import collections
import ctypes as C
import sqlite3
import struct
import sys
from ctypes import wintypes as W

MODULE_SNAPSHOT = 0x00000008 | 0x00000010
LIST_MODULES_ALL = 0x03


def live_modules(pid):
    """Возвращает список (start, end, name) модулей процесса."""
    k32 = C.WinDLL("kernel32", use_last_error=True)
    k32.CreateToolhelp32Snapshot.restype = W.HANDLE

    class ME32(C.Structure):
        _fields_ = [
            ("dwSize", W.DWORD), ("th32ModuleID", W.DWORD), ("th32ProcessID", W.DWORD),
            ("GlblcntUsage", W.DWORD), ("ProccntUsage", W.DWORD),
            ("modBaseAddr", C.POINTER(C.c_ubyte)), ("modBaseSize", W.DWORD),
            ("hModule", W.HMODULE), ("szModule", W.WCHAR * 256), ("szExePath", W.WCHAR * 260),
        ]

    snap = k32.CreateToolhelp32Snapshot(MODULE_SNAPSHOT, pid)
    if snap == W.HANDLE(-1).value:
        return []
    out = []
    me = ME32()
    me.dwSize = C.sizeof(me)
    if k32.Module32FirstW(snap, C.byref(me)):
        while True:
            start = C.cast(me.modBaseAddr, C.c_void_p).value or 0
            out.append((start, start + me.modBaseSize, me.szModule))
            if not k32.Module32NextW(snap, C.byref(me)):
                break
    k32.CloseHandle(snap)
    return out


class FuncTable:
    """rva -> (name, size) с бинарным поиском по отсортированным rva."""

    def __init__(self, db_path):
        con = sqlite3.connect(db_path)
        rows = con.execute(
            "SELECT rva, name, size FROM fn WHERE tag=5 ORDER BY rva"
        ).fetchall()
        con.close()
        # дубликаты rva (перегрузки) — оставляем самую длинную
        best = {}
        for rva, name, size in rows:
            if rva in best:
                if len(name) > len(best[rva][0]):
                    best[rva] = (name, size)
            else:
                best[rva] = (name, size)
        items = sorted(best.items())
        self.rvas = [r for r, _ in items]
        self.info = [(n, s if s > 0 else 0x40) for _, (n, s) in items]

    def lookup(self, rva):
        i = bisect.bisect_right(self.rvas, rva) - 1
        if i < 0:
            return None
        r0 = self.rvas[i]
        name, size = self.info[i]
        if rva < r0 + size:
            return name
        return None


def short_class(name):
    """UWorld::Tick -> UWorld ; namespace::func -> namespace."""
    idx = name.rfind("::")
    return name[:idx] if idx > 0 else "(global)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bin")
    ap.add_argument("--db", default=r"C:\Dev\_research\v361.sqlite")
    ap.add_argument("--top", type=int, default=40)
    ap.add_argument("--pid", type=int, default=0)
    ap.add_argument("--modules", default="", help="prof_*.modules.txt рядом с профилем")
    ap.add_argument("--exclude-idle", action="store_true",
                    help="выбросить сэмплы в заглушках системных вызовов (Sleep/Wait): это стена, а не CPU")
    args = ap.parse_args()

    with open(args.bin, "rb") as f:
        base, count = struct.unpack("<QQ", f.read(16))
        data = f.read(8 * count)
    rips = struct.unpack("<%dQ" % count, data)
    print("samples: %d, image base: 0x%X" % (count, base))

    table = FuncTable(args.db)
    mods = []
    mod_file = args.modules
    if not mod_file:
        cand = args.bin.rsplit(".", 1)[0] + ".modules.txt"
        mod_file = cand if os.path.exists(cand) else ""
    if mod_file and os.path.exists(mod_file):
        with open(mod_file, "r", encoding="utf-8", errors="replace") as f:
            next(f, None)
            for line in f:
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 3:
                    continue
                try:
                    start = int(parts[0], 16)
                    size = int(parts[1], 16)
                except ValueError:
                    continue
                mods.append((start, start + size, parts[2].split("\\")[-1]))
    elif args.pid:
        mods = live_modules(args.pid)
    mods = sorted(mods)
    mod_starts = [m[0] for m in mods]

    # Заглушки системных вызовов ntdll: попадание туда = поток спит/ждёт,
    # а не выполняет код игры. Отрезок 0x15E000..0x160000 — NtDelayExecution,
    # NtWaitForSingleObject и соседние (проверено дизассемблированием ntdll).
    idle_lo = 0x15E000
    idle_hi = 0x160000

    def is_idle(name):
        if not name.startswith("[ntdll.dll+"):
            return False
        try:
            off = int(name.split("+0x")[1].rstrip("]"), 16)
        except (IndexError, ValueError):
            return False
        return idle_lo <= off <= idle_hi

    self_counts = collections.Counter()
    class_counts = collections.Counter()
    unknown = 0
    idle = 0
    for rip in rips:
        rva = rip - base
        name = table.lookup(rva) if 0 <= rva < 0x8000000 else None
        if name:
            self_counts[name] += 1
            class_counts[short_class(name)] += 1
        else:
            if mods:
                i = bisect.bisect_right(mod_starts, rip) - 1
                if i >= 0 and rip < mods[i][1]:
                    label = "[%s+0x%X]" % (mods[i][2], rip - mods[i][0])
                    if args.exclude_idle and is_idle(label):
                        idle += 1
                        continue
                    self_counts[label] += 1
                    class_counts["(external module)"] += 1
                    continue
            unknown += 1
            self_counts["<unknown 0x%X>" % (rva if 0 <= rva < 0x8000000 else rip)] += 1
            class_counts["(unknown)"] += 1

    total = count or 1
    if args.exclude_idle:
        print("idle (Sleep/Wait in ntdll): %d samples = %.1f%% of wall time\n"
              % (idle, 100.0 * idle / total))
        total = count - idle
        print("=> ниже распределение только по исполняемому коду (%d сэмплов)\n" % total)
    print("resolved in image: %.1f%%, external: %.1f%%, unknown: %.1f%%\n" % (
        100.0 * sum(v for k, v in self_counts.items() if not k.startswith("[") and not k.startswith("<")) / total,
        100.0 * class_counts.get("(external module)", 0) / total,
        100.0 * class_counts.get("(unknown)", 0) / total,
    ))

    print("=== TOP %d self time ===" % args.top)
    print("%-6s %-9s %s" % ("cnt", "share", "function"))
    for name, c in self_counts.most_common(args.top):
        print("%-6d %6.2f%%  %s" % (c, 100.0 * c / total, name))

    print("\n=== TOP %d by class ===" % args.top)
    for name, c in class_counts.most_common(args.top):
        print("%-6d %6.2f%%  %s" % (c, 100.0 * c / total, name))


if __name__ == "__main__":
    main()
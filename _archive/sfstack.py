# -*- coding: utf-8 -*-
"""
Разбор стек-сэмплов, собранных внутри окна FTickTaskManager::StartFrame.

Файл: prof_<t>.sfstack = [u64 count][count * (rip, ret, sp1..sp4)]

    python sfstack.py <file.sfstack> [--top 15]
"""
import argparse
import bisect
import collections
import os
import sqlite3
import struct
import sys

WORDS = 6


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--top", type=int, default=15)
    args = ap.parse_args()

    con = sqlite3.connect(r"C:\Dev\_research\v361.sqlite")
    rows = con.execute("SELECT rva, name, size FROM fn WHERE tag=5 ORDER BY rva").fetchall()
    con.close()
    rvas = [r for r, n, s in rows]
    info = [(n, s if s > 0 else 0x40) for r, n, s in rows]

    def look(addr, base):
        rva = addr - base
        i = bisect.bisect_right(rvas, rva) - 1
        if i >= 0 and rva < rvas[i] + info[i][1]:
            return info[i][0]
        return None

    with open(args.path, "rb") as f:
        data = f.read()
    count = struct.unpack_from("<Q", data, 0)[0]
    print("стек-сэмплов: %d\n" % count)

    # база образа из .modules.txt рядом
    base = None
    mods = args.path.rsplit(".", 1)[0] + ".modules.txt"
    if os.path.exists(mods):
        with open(mods, encoding="utf-8", errors="replace") as f:
            next(f, None)
            for ln in f:
                p = ln.split("\t")
                if len(p) >= 3 and p[2].lower().endswith("shootergameserver.exe"):
                    base = int(p[0], 16)
    if base is None:
        companion = args.path.replace(".sfstack", ".bin")
        if os.path.exists(companion):
            with open(companion, "rb") as f:
                base = struct.unpack("<Q", f.read(8))[0]
            print("база образа взята из .bin: 0x%X" % base)
        else:
            print("нет ни modules.txt, ни .bin рядом — имена не разрешатся")
            return 1

    leaves = collections.Counter()
    callers = collections.Counter()
    outside = 0
    for i in range(count):
        off = 8 + i * WORDS * 8
        rip, ret, s1, s2, s3, s4 = struct.unpack_from("<6Q", data, off)
        nm = look(rip, base)
        if nm is None:
            nm = "[вне образа] +0x%X" % (rip - base) if rip > base else "[вне образа]"
            outside += 1
        leaves[nm] += 1
        # самый глубокий кадр, который ещё принадлежит нашему образу
        for a in (ret, s1, s2, s3, s4):
            c = look(a, base)
            if c:
                callers[c] += 1
                break

    tot = sum(leaves.values())
    print("=== где находится RIP внутри окна StartFrame ===")
    for nm, c in leaves.most_common(args.top):
        print("   %5.1f%%  %s" % (100.0 * c / tot, nm[:72]))
    print("\n=== ближайший кадр нашего образа (кто вызывает) ===")
    for nm, c in callers.most_common(args.top):
        print("   %5.1f%%  %s" % (100.0 * c / tot, nm[:72]))
    print("\nсэмплов вне образа: %d (%.1f%%)" % (outside, 100.0 * outside / tot))
    return 0


if __name__ == "__main__":
    sys.exit(main())
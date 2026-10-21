# -*- coding: utf-8 -*-
"""
Разбор prof_*.wait — сэмплов GameThread, застрявших в системном вызове.

Формат: [u64 count][count * (rip, sp0, sp1, sp2, sp3)]
RIP вне пользовательских модулей = поток в syscall. В стеке ищем адреса,
попавшие в образ игры, и восстанавливаем цепочку вызовов.

    python waitstack.py <file.wait> [--top 15]
"""
import argparse
import bisect
import collections
import os
import sqlite3
import struct
import sys

WORDS = 5


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

    def look(rva):
        i = bisect.bisect_right(rvas, rva) - 1
        if i >= 0 and rva < rvas[i] + info[i][1]:
            return info[i][0]
        return None

    with open(args.path, "rb") as f:
        data = f.read()
    count = struct.unpack_from("<Q", data, 0)[0]
    print("сэмплов ожидания: %d\n" % count)

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
        # база образа лежит в заголовке .bin: [base][count][rips...]
        companion = args.path.replace(".wait", ".bin")
        if os.path.exists(companion):
            with open(companion, "rb") as f:
                base = struct.unpack("<Q", f.read(8))[0]
            print("база образа взята из %s: 0x%X" % (os.path.basename(companion), base))
        else:
            print("нет ни modules.txt, ни .bin рядом — имена не разрешатся")
            return 1

    rips = collections.Counter()
    chains = collections.Counter()
    callers = collections.Counter()
    for i in range(count):
        off = 8 + i * WORDS * 8
        rip, s0, s1, s2, s3 = struct.unpack_from("<5Q", data, off)
        rips[rip] += 1
        chain = []
        for w in (s0, s1, s2, s3):
            if base < w < base + 0x8000000:
                nm = look(w - base)
                if nm:
                    chain.append(nm)
                    if len(chain) >= 4:
                        break
        if chain:
            callers[chain[0]] += 1
            chains[" <- ".join(chain)] += 1
        else:
            chains["<нет кадров игры в стеке>"] += 1

    # имена модулей, чтобы отличать заглушки вызовов от работы движка
    mods = []
    if os.path.exists(mods_path := args.path.rsplit(".", 1)[0] + ".modules.txt"):
        with open(mods_path, encoding="utf-8", errors="replace") as f:
            next(f, None)
            for ln in f:
                p2 = ln.split("\t")
                if len(p2) >= 3:
                    s0 = int(p2[0], 16)
                    mods.append((s0, s0 + int(p2[1], 16), p2[2].split("\\")[-1]))

    def modof(v):
        for s0, e0, n in mods:
            if s0 <= v < e0:
                return n
        return "ядро"

    print("=== RIP: где именно заблокирован поток ===")
    agg = collections.Counter()
    for rip, c in rips.items():
        agg[modof(rip)] += c
    for n, c in agg.most_common(8):
        print("   %5.1f%%  %s" % (100.0 * c / count, n))
    print()
    for rip, c in rips.most_common(8):
        print("   %5.1f%%  %016X  %s" % (100.0 * c / count, rip, modof(rip)))

    print("\n=== ближайший кадр игры (кто вызывает ожидание) ===")
    for nm, c in callers.most_common(args.top):
        print("   %5.1f%%  %s" % (100.0 * c / count, nm[:72]))

    print("\n=== цепочки вызовов ===")
    for ck, c in chains.most_common(args.top):
        print("   %5.1f%%  %s" % (100.0 * c / count, ck[:150]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
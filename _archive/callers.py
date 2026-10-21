# -*- coding: utf-8 -*-
"""
Атрибуция вызовов по грубой выборке: для каждого "листа" показывает, кто его зовёт.

    python callers.py <prof.bin> [--ret prof.ret] [--top 25]

Использует пары (RIP, [RSP]) из сэмплера: для горячих листовых функций
значение на стеке — адрес возврата, то есть вызывающий.
"""
import argparse
import bisect
import collections
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from symbolize import FuncTable  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bin")
    ap.add_argument("--db", default=r"C:\Dev\_research\v361.sqlite")
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--min-share", type=float, default=0.2)
    args = ap.parse_args()

    ret_path = args.bin.rsplit(".", 1)[0] + ".ret"

    with open(args.bin, "rb") as f:
        base, count = struct.unpack("<QQ", f.read(16))
        rips = struct.unpack("<%dQ" % count, f.read(8 * count))
    rets = ()
    if os.path.exists(ret_path):
        with open(ret_path, "rb") as f:
            data = f.read(8 * count)
        rets = struct.unpack("<%dQ" % count, data)
    else:
        print("нет файла %s — атрибуция вызовов невозможна" % ret_path)
        return 1

    syms = FuncTable(args.db)
    leaf_calls = collections.defaultdict(collections.Counter)
    for rip, ret in zip(rips, rets):
        rva = rip - base
        leaf = syms.lookup(rva) if 0 <= rva < 0x8000000 else None
        if not leaf:
            continue
        caller = syms.lookup(ret - base) if ret else None
        leaf_calls[leaf][caller or "<ret вне образа>"] += 1

    total = sum(sum(c.values()) for c in leaf_calls.values())
    print("сэмплов в образе: %d, уникальных листьев: %d\n" % (total, len(leaf_calls)))

    ranked = sorted(leaf_calls.items(), key=lambda kv: -sum(kv[1].values()))
    for leaf, callers in ranked[:args.top]:
        cnt = sum(callers.values())
        if 100.0 * cnt / total < args.min_share:
            continue
        print("%s  — %.2f%% образца" % (leaf, 100.0 * cnt / total))
        for caller, c in callers.most_common(6):
            print("     %6.2f%%  <- %s" % (100.0 * c / cnt, caller))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
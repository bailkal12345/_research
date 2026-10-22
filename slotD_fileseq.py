# -*- coding: utf-8 -*-
# File IO attribution: sequence of wait leaves.
# If directory reads are our own .ark polling (1 Hz), records come in BURSTS
# (dozens in a row) with an even ~1 s step. If it is the engine - bursts are rarer.
import collections
import os
import struct
import sys

sys.path.insert(0, r'C:\Dev\_research')
import profanalyze as pa

TICKPROF = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi\Plugins\_backup\TickProf'


def main():
    prof = sys.argv[1]
    mods, bases = pa.load_modules(os.path.join(TICKPROF, 'prof_%s.modules.txt' % prof))
    ex = {}
    for base, size, short, full, is_sys in mods:
        key = short.lower()
        if key not in ex:
            try:
                ex[key] = pa.ExportIndex(full)
            except Exception:
                ex[key] = None
    data = open(os.path.join(TICKPROF, 'prof_%s.wait' % prof), 'rb').read()
    cnt = struct.unpack_from('<Q', data, 0)[0]
    words, base = 5, 8
    if len(data) >= 16:
        w2 = struct.unpack_from('<Q', data, 8)[0]
        if 0 < w2 <= 32:
            words, base = w2, 16
    raw = struct.unpack_from('<%dQ' % (cnt * words), data, base)
    leaves = []
    for i in range(cnt):
        rec = raw[i * words:(i + 1) * words]
        short, off, is_sys = pa.mod_of(rec[0], mods, bases)
        nm = None
        if short and ex.get(short.lower()):
            nm = ex[short.lower()].name_of(off)
        leaves.append(nm or ('%s+0x%s' % (short, ('None' if off is None else hex(off)))))

    # runs of identical leaves
    runs = []
    cur = leaves[0]
    ln = 1
    for x in leaves[1:]:
        if x == cur:
            ln += 1
        else:
            runs.append((cur, ln))
            cur = x
            ln = 1
    runs.append((cur, ln))

    print('=== profile %s: %d wait records ===' % (prof, cnt))
    print('\n--- top leaves ---')
    for k, v in collections.Counter(leaves).most_common(10):
        print('%8d  %s' % (v, k))

    print('\n--- runs for file IO ---')
    io_runs = [(k, v, i) for i, (k, v) in enumerate(runs) if 'Directory' in k or 'Find' in k or 'Query' in k]
    print('total IO runs: %d, records in them: %d' % (len(io_runs), sum(v for _, v, _ in io_runs)))
    for k, v, i in io_runs[:25]:
        print('  run #%d: %-40s len=%d (position in the sequence %d)' % (i, k, v, i))

    print('\n--- count of IO runs and sum of lengths ---')
    lens = [v for _, v, _ in io_runs]
    if lens:
        print('runs=%d, mean length=%.1f, max=%d, total=%d' %
              (len(lens), sum(lens) / len(lens), max(lens), sum(lens)))

    print('\n--- step between IO runs (in records) ---')
    idx = [i for _, _, i in io_runs]
    gaps = [b - a for a, b in zip(idx, idx[1:])]
    if gaps:
        print('steps: min=%d max=%d median=%d, first 20: %s' %
              (min(gaps), max(gaps), sorted(gaps)[len(gaps) // 2], gaps[:20]))


if __name__ == '__main__':
    main()

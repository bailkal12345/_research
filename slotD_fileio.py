# -*- coding: utf-8 -*-
# Атрибуция файлового IO фазы (приоритет 2 doit6 22.10), v2:
#  * резолвим имена системных листьев через таблицу экспортов DLL;
#  * для каждой записи ожидания восстанавливаем цепочку вызывающих по словам
#    стека (12 слов), ищем ПЕРВЫЙ кадр exe - это владелец ожидания;
#  * отдельно: дамп сырых записей для листа файлового IO (ZwQueryDirectoryFileEx).
import bisect
import collections
import os
import struct
import sys

sys.path.insert(0, r'C:\Dev\_research')
import profanalyze as pa

TICKPROF = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi\Plugins\_backup\TickProf'
GHIDRA = r'C:\Dev\_research\ghidra_funcs_v361.tsv'
EXE = 'shootergameserver.exe'


def load_modules(path):
    mods = []
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            p = line.split()
            if len(p) < 3 or p[0].lower().startswith('base'):
                continue
            try:
                base = int(p[0], 16)
                size = int(p[1], 16)
            except ValueError:
                continue
            mods.append((base, size, p[2]))
    return mods


def load_ghidra():
    rows = []
    with open(GHIDRA, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            p = line.rstrip('\n').split('\t')
            if len(p) < 3:
                continue
            try:
                rows.append((int(p[0], 16), int(p[2], 16), p[1]))
            except ValueError:
                continue
    rows.sort()
    return rows, [r[0] for r in rows]


def main():
    prof = sys.argv[1] if len(sys.argv) > 1 else '687851390'
    dump_leaf = sys.argv[2] if len(sys.argv) > 2 else None
    mods = load_modules(os.path.join(TICKPROF, 'prof_%s.modules.txt' % prof))
    ghidra, gstarts = load_ghidra()
    ex_idx = {}
    for base, size, full in mods:
        short = os.path.basename(full).lower()
        if short not in ex_idx:
            try:
                ex_idx[short] = pa.ExportIndex(full)
            except Exception:
                ex_idx[short] = None

    def mod_of(addr):
        for base, size, full in mods:
            if base <= addr < base + size:
                return os.path.basename(full).lower(), addr - base, full
        return None, None, None

    def sys_name(short, off):
        idx = ex_idx.get(short)
        if idx:
            nm = idx.name_of(off)
            if nm:
                return nm
        return '%s+0x%X' % (short, off)

    def exe_name(rva):
        i = bisect.bisect_right(gstarts, rva) - 1
        if i >= 0:
            s, sz, nm = ghidra[i]
            if rva < s + sz:
                return '%s+0x%x' % (nm, rva - s)
        return 'rva 0x%X' % rva

    data = open(os.path.join(TICKPROF, 'prof_%s.wait' % prof), 'rb').read()
    cnt, words = struct.unpack_from('<QQ', data, 0)
    raw = struct.unpack_from('<%dQ' % (cnt * words), data, 16)
    print('=== профиль %s: записей ожидания %d, слов %d ===' % (prof, cnt, words))

    leaf_counter = collections.Counter()
    owner_counter = collections.defaultdict(collections.Counter)
    chain_counter = collections.Counter()
    dumps = []
    for i in range(cnt):
        rec = raw[i * words:(i + 1) * words]
        short, off, full = mod_of(rec[0])
        if short is None:
            continue
        leaf = sys_name(short, off)
        leaf_counter[leaf] += 1
        chain = []
        exe_frames = []
        for w in rec[1:]:
            if not w:
                continue
            s2, o2, f2 = mod_of(w)
            if s2 is None:
                chain.append('%012X(?)' % w)
                continue
            if s2 == EXE:
                chain.append('EXE:' + exe_name(o2))
                exe_frames.append(o2)
            else:
                chain.append(sys_name(s2, o2))
        if exe_frames:
            owner_counter[leaf][exe_name(exe_frames[0])] += 1
        chain_counter[' -> '.join(chain[:6])] += 1
        if dump_leaf and leaf.lower().find(dump_leaf.lower()) >= 0 and len(dumps) < 4:
            dumps.append(rec)

    print('\n--- топ-20 листьев ожидания ---')
    for k, v in leaf_counter.most_common(20):
        print('%8d  %s' % (v, k))

    print('\n--- владелец (первый exe-кадр) ---')
    for leaf, _ in leaf_counter.most_common(14):
        if leaf not in owner_counter:
            print('\nлист %s (%d): exe-кадра нет' % (leaf, leaf_counter[leaf]))
            continue
        print('\nлист %s (%d записей):' % (leaf, leaf_counter[leaf]))
        for own, c2 in owner_counter[leaf].most_common(8):
            print('    %6d  %s' % (c2, own))

    print('\n--- топ-25 цепочек ---')
    for k, v in chain_counter.most_common(25):
        print('%8d  %s' % (v, k))

    if dumps:
        print('\n--- сырые записи для %s ---' % dump_leaf)
        for rec in dumps:
            print('  ' + ' '.join('%012X' % w for w in rec))


if __name__ == '__main__':
    main()

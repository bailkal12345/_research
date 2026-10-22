# -*- coding: utf-8 -*-
# Атрибуция файлового IO: последовательность листьев ожидания.
# Если чтение каталога - наш собственный опрос .ark (1 Гц), записи идут ПАЧКАМИ
# (десятки подряд) с равномерным шагом ~1 с. Если это движок - пачки реже/реже.
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

    # пачки одинаковых листьев
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

    print('=== профиль %s: %d записей ожидания ===' % (prof, cnt))
    print('\n--- топ листьев ---')
    for k, v in collections.Counter(leaves).most_common(10):
        print('%8d  %s' % (v, k))

    print('\n--- пачки (run) для файлового IO ---')
    io_runs = [(k, v, i) for i, (k, v) in enumerate(runs) if 'Directory' in k or 'Find' in k or 'Query' in k]
    print('всего пачек IO: %d, записей в них: %d' % (len(io_runs), sum(v for _, v, _ in io_runs)))
    for k, v, i in io_runs[:25]:
        print('  пачка #%d: %-40s len=%d (позиция в последовательности %d)' % (i, k, v, i))

    print('\n--- число пачек IO и сумма длин ---')
    lens = [v for _, v, _ in io_runs]
    if lens:
        print('пачек=%d, средняя длина=%.1f, макс=%d, всего=%d' %
              (len(lens), sum(lens) / len(lens), max(lens), sum(lens)))

    print('\n--- шаг между пачками IO (в записях) ---')
    idx = [i for _, _, i in io_runs]
    gaps = [b - a for a, b in zip(idx, idx[1:])]
    if gaps:
        print('шаги: min=%d max=%d медиана=%d, первые 20: %s' %
              (min(gaps), max(gaps), sorted(gaps)[len(gaps) // 2], gaps[:20]))


if __name__ == '__main__':
    main()

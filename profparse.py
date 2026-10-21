# -*- coding: utf-8 -*-
# Разбор профайл-файлов TickProf (бинарные стеки) по modules.txt.
# Только чтение существующих артефактов; никакой записи на сервер.
import struct, sys, collections, io

TICKPROF = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi\Plugins\TickProf'
OUT = r'C:\Dev\_research\prof_report.txt'

def load_modules(path):
    mods = []
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            p = line.split('\t')
            if len(p) >= 3:
                try:
                    base = int(p[0], 16); size = int(p[1], 16)
                except ValueError:
                    continue
                mods.append((base, size, p[2].strip()))
    mods.sort()
    return mods

def classify(addr, mods):
    import bisect
    i = bisect.bisect_right([m[0] for m in mods], addr) - 1
    if i >= 0:
        base, size, name = mods[i]
        if addr < base + size:
            short = name.replace('\\', '/').split('/')[-1]
            off = addr - base
            return '%s+0x%X' % (short, off)
    return 'UNKNOWN+0x%X' % addr

def main():
    mods = load_modules(TICKPROF + r'\prof_512222984.modules.txt')
    buf = []
    for ext in ('bin', 'wait', 'ret'):
        data = open(TICKPROF + r'\prof_512222984.' + ext, 'rb').read()
        buf.append('%s: %d байт, делится на 8: %s' % (ext, len(data), len(data) % 8 == 0))
        u64s = struct.unpack('<%dQ' % (len(data) // 8), data[:len(data) // 8 * 8])
        zeros = sum(1 for v in u64s if v == 0)
        buf.append('%s: u64=%d, нулей=%d, первых 12 адресов:' % (ext, len(u64s), zeros))
        for v in u64s[:12]:
            buf.append('   %016X  %s' % (v, classify(v, mods) if v else 'NULL'))
        # корявые маленькие значения (не адреса) — поиск признака заголовка
        small = sum(1 for v in u64s if 0 < v < 0x10000)
        buf.append('%s: маленьких значений (<0x10000, не адреса)=%d' % (ext, small))
    # Гипотеза: каждый сэмпл = [счётчик/глубина? затем адреса до нуля?]
    data = open(TICKPROF + r'\prof_512222984.bin', 'rb').read()
    u64s = struct.unpack('<%dQ' % (len(data) // 8), data[:len(data) // 8 * 8])
    # найти позиции нулей
    zpos = [i for i, v in enumerate(u64s) if v == 0]
    buf.append('bin: позиций нулей=%d, первые 20: %s' % (len(zpos), zpos[:20]))
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(buf))
    print('\n'.join(buf))

if __name__ == '__main__':
    main()

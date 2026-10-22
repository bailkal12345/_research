# -*- coding: utf-8 -*-
# Слот A (v6): кросс-табуляция "слово exe в стеке" x "ближайший exe-сэмпл".
# Цель: назвать владельца для кластера &GNatives (слот[3] = 0x1491C6B0) и проверить
# метод на известном кластере TaskGraph (слот[3] = ProcessTasksNamedThread+0x32d).
import struct, collections, sys, json
sys.stdout.reconfigure(encoding='utf-8')

TICKPROF = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi\Plugins\_backup\TickProf'
import profanalyze as pa
import profnamed as pn

TXT = 0x391AA6E
mods, bases = pa.load_modules(TICKPROF + r'\prof_512222984.modules.txt')
ghidra, gstarts = pn.load_ghidra_names()
namer = pn.Namer(ghidra, gstarts)

PROF = '512222984'
bdata = open(TICKPROF + r'\prof_%s.bin' % PROF, 'rb').read()
wdata = open(TICKPROF + r'\prof_%s.wait' % PROF, 'rb').read()
ns = len(bdata) // 8
rips = struct.unpack_from('<%dQ' % ns, bdata, 0)
wcnt = struct.unpack_from('<Q', wdata, 0)[0]
wwords = struct.unpack_from('<%dQ' % (wcnt * 5), wdata, 8)


def mi(a):
    return pa.mod_of(a, mods, bases)


def blocked(r):
    short, off, issys = mi(r)
    return True if short is None else bool(issys)


def exe_fn(a):
    short, off, _ = mi(a)
    if short == 'ShooterGameServer.exe' and off < TXT:
        return namer.name(off) or ('sub_%X' % off)
    return None


def exe_data(a):
    short, off, _ = mi(a)
    if short == 'ShooterGameServer.exe' and off >= TXT:
        return 'exeDATA+0x%X' % off
    return None


pairs = []
k = 0
for i in range(ns):
    if blocked(rips[i]):
        if k < wcnt and wwords[k * 5] == rips[i]:
            pairs.append((i, k))
            k += 1
print('выровнено %d/%d' % (len(pairs), wcnt))

# группировка по содержимому exe-слов
groups = collections.defaultdict(list)
for (i, k) in pairs:
    w = wwords[k * 5:k * 5 + 5]
    sig = []
    for a in w:
        f = exe_fn(a)
        d = exe_data(a)
        if f:
            sig.append(f)
        elif d:
            sig.append(d)
        else:
            sig.append(None)
    key = tuple(sig)
    groups[key].append((i, k))

print('\n=== группы по exe-словам стека (wait=%d) ===' % len(pairs))
for key, lst in sorted(groups.items(), key=lambda kv: -len(kv[1])):
    if not any(key):
        continue
    print('\n  ГРУППА %d записей: %s' % (len(lst), [x if x else '-' for x in key]))
    # контекст: ближайший exe-сэмпл ДО и ПОСЛЕ
    bef = collections.Counter()
    aft = collections.Counter()
    for (i, k) in lst:
        pj = None
        for j in range(i - 1, max(-1, i - 4), -1):
            f = exe_fn(rips[j])
            if f:
                pj = f
                break
        nj = None
        for j in range(i + 1, min(ns, i + 4)):
            f = exe_fn(rips[j])
            if f:
                nj = f
                break
        bef[pj or '<?>'] += 1
        aft[nj or '<?>'] += 1
    print('     до:  ' + ', '.join('%s=%d' % (a, b) for a, b in bef.most_common(6)))
    print('     после: ' + ', '.join('%s=%d' % (a, b) for a, b in aft.most_common(6)))

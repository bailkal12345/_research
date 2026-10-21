# -*- coding: utf-8 -*-
# Слот A (v2): именованная атрибуция wait'ов dense-профиля.
# Идея: .bin и .wait пишутся в одном цикле сэмплера => wait[k] соответствует
# k-му "заблокированному" сэмплу (критерий RipIsBlocked как в плагине).
# Для каждого wait'а берём СЛЕДУЮЩИЙ exe-сэмпл: это код, в который поток вернулся
# после ожидания => вызывающий (владелец блокировки).
import struct, collections, sys, json
sys.stdout.reconfigure(encoding='utf-8')

TICKPROF = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi\Plugins\_backup\TickProf'
import profanalyze as pa
import profnamed as pn

TXT = 0x391AA6E
mods, bases = pa.load_modules(TICKPROF + r'\prof_512222984.modules.txt')
ghidra, gstarts = pn.load_ghidra_names()
namer = pn.Namer(ghidra, gstarts)


def modinfo(a):
    return pa.mod_of(a, mods, bases)


def loc(a):
    short, off, issys = modinfo(a)
    if short == 'ShooterGameServer.exe':
        if off >= TXT:
            return 'exe@Data+%x' % off
        return 'exe:0x%X %s' % (off, namer.name(off) or ('sub_%X' % off))
    if short:
        return '%s+%x' % (short, off)
    return 'raw_%x' % a


def fname(rva):
    return namer.name(rva) or ('sub_%X' % rva)


def rip_is_blocked(r):
    """RipIsBlocked из TickProf.cpp: модуль известен и is_sys -> True; неизвестен -> True."""
    short, off, issys = modinfo(r)
    if short is None:
        return True
    return bool(issys)


PROF = sys.argv[1] if len(sys.argv) > 1 else '512222984'
bdata = open(TICKPROF + r'\prof_%s.bin' % PROF, 'rb').read()
wdata = open(TICKPROF + r'\prof_%s.wait' % PROF, 'rb').read()
ns = len(bdata) // 8
rips = struct.unpack_from('<%dQ' % ns, bdata, 0)
wcnt = struct.unpack_from('<Q', wdata, 0)[0]
wwords = struct.unpack_from('<%dQ' % (wcnt * 5), wdata, 8)
print('профиль %s: сэмплов=%d wait=%d' % (PROF, ns, wcnt))

# сопоставление
pairs = []
k = 0
bad = 0
for i in range(ns):
    if rip_is_blocked(rips[i]):
        if k < wcnt and wwords[k * 5] == rips[i]:
            pairs.append((i, k))
            k += 1
        else:
            bad += 1
            if bad < 4:
                print('  расхождение: сэмпл %d rip=%s ; wait[%d].rip=%s' % (
                    i, loc(rips[i]), k, loc(wwords[k * 5]) if k < wcnt else '-'))
            if bad > 200:
                break
print('выровнено: %d из %d wait (k=%d, расхождений=%d)' % (len(pairs), wcnt, k, bad))

# следующий exe-сэмпл после wait
def next_exe(i, span=3):
    for j in range(i + 1, min(ns, i + 1 + span)):
        short, off, _ = modinfo(rips[j])
        if short == 'ShooterGameServer.exe' and off < TXT:
            return j, off
    return None, None


owners = collections.Counter()
owners_sys = collections.Counter()
rows = []
for (i, k) in pairs:
    j, off = next_exe(i)
    wctx = [loc(x) for x in wwords[k * 5:k * 5 + 5]]
    # кто в exe: имя функции
    own = fname(off) if off is not None else '<нет exe-сэмпла рядом>'
    owners[own] += 1
    # syscall-класс по rip wait
    short, woff, _ = modinfo(wwords[k * 5])
    sysc = ('%s+%x' % (short, woff)) if short else 'unknown'
    owners_sys[(sysc, own)] += 1
    rows.append((i, k, own, sysc, wctx))

print('\n=== владелец ожидания (следующий exe-сэмпл) ===')
tot = len(pairs)
for own, c in owners.most_common(30):
    print('  %5d (%5.1f%%)  %s' % (c, 100.0 * c / tot, own))

print('\n=== syscall x владелец (топ-25) ===')
for (sysc, own), c in owners_sys.most_common(25):
    print('  %5d (%5.1f%%)  %-24s %s' % (c, 100.0 * c / tot, sysc, own))

with open(TICKPROF + ('\\prof_%s.waitowners.json' % PROF), 'w', encoding='utf-8') as f:
    json.dump(rows, f, ensure_ascii=False)
print('\n-> %s' % (TICKPROF + ('\\prof_%s.waitowners.json' % PROF)))

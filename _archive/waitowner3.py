# -*- coding: utf-8 -*-
# Слот A (v10): владелец ожидания = вызывающий FEvent::Wait.
#
# Идея: когда ожидание заканчивается, управление возвращается в FWindowsEvent::Wait
# (0x1F5BBB0) -> его [RSP] = адрес возврата В ВЫЗЫВАЮЩИЙ (виртуальный вызов FEvent::Wait).
# Поэтому: первый exe-сэмпл после wait'а, если он лежит внутри FWindowsEvent::Wait,
# даёт нам ИМЯ владельца ожидания.
import struct, collections, sys
sys.stdout.reconfigure(encoding='utf-8')

TICKPROF = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi\Plugins\_backup\TickProf'
import profanalyze as pa
import profnamed as pn

TXT = 0x391AA6E
mods, bases = pa.load_modules(TICKPROF + r'\prof_512222984.modules.txt')
ghidra, gstarts = pn.load_ghidra_names()
namer = pn.Namer(ghidra, gstarts)

PROF = sys.argv[1] if len(sys.argv) > 1 else '512222984'
bdata = open(TICKPROF + r'\prof_%s.bin' % PROF, 'rb').read()
rdata = open(TICKPROF + r'\prof_%s.ret' % PROF, 'rb').read()
wdata = open(TICKPROF + r'\prof_%s.wait' % PROF, 'rb').read()
ns = len(bdata) // 8
rips = struct.unpack_from('<%dQ' % ns, bdata, 0)
nret = len(rdata) // 8
rets = struct.unpack_from('<%dQ' % nret, rdata, 0)
wcnt = struct.unpack_from('<Q', wdata, 0)[0]
wwords = struct.unpack_from('<%dQ' % (wcnt * 5), wdata, 8)


def mi(a):
    return pa.mod_of(a, mods, bases)


def blocked(r):
    short, off, issys = mi(r)
    return True if short is None else bool(issys)


def exe_rva(a):
    short, off, _ = mi(a)
    if short == 'ShooterGameServer.exe' and off < TXT:
        return off
    return None


def fn(rva):
    return namer.name(rva) or ('sub_%X' % rva)


pairs = []
k = 0
for i in range(ns):
    if blocked(rips[i]):
        if k < wcnt and wwords[k * 5] == rips[i]:
            pairs.append((i, k))
            k += 1
print('профиль %s: сэмплов=%d wait=%d выровнено=%d' % (PROF, ns, wcnt, len(pairs)))

# диапазон FWindowsEvent::Wait (по Ghidra: 0x1F5BBB0, размер 138)
FWAIT_LO, FWAIT_HI = 0x1F5BBB0, 0x1F5BBB0 + 0x8A

owner = collections.Counter()
leaf_after = collections.Counter()
hit_fwait = 0
for (i, k) in pairs:
    j = None
    for x in range(i + 1, min(ns, i + 1 + 12)):
        if exe_rva(rips[x]) is not None:
            j = x
            break
    if j is None:
        owner['<?>'] += 1
        continue
    r = exe_rva(rips[j])
    leaf_after[fn(r)] += 1
    if FWAIT_LO <= r < FWAIT_HI:
        hit_fwait += 1
        if j < nret:
            rv = exe_rva(rets[j])
            owner[fn(rv) if rv is not None else 'non-exe:%s' % hex(rets[j])] += 1
        else:
            owner['<?>'] += 1
    else:
        owner['<leaf после ожидания: %s>' % fn(r)] += 1

tot = len(pairs)
print('\n=== владелец ожидания ===')
for o, c in owner.most_common(35):
    print('  %5d (%5.1f%%)  %s' % (c, 100.0 * c / tot, o))
print('\nпервый exe-сэмпл после ожидания (leaf):')
for o, c in leaf_after.most_common(12):
    print('  %5d  %s' % (c, o))
named = sum(c for o, c in owner.items() if o and not o.startswith('<') and o != '<?>')
print('\nназвано владельцем (FWindowsEvent::Wait-кадр): %d из %d (%.1f%%)' % (named, tot, 100.0 * named / tot))

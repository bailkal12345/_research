# -*- coding: utf-8 -*-
# Слот A (v7): владелец ожидания по цепочке (RIP, [RSP]) из .bin/.ret.
# Для каждого wait-сэмпла идём назад по потоку сэмплов, берём последний exe-сэмпл
# (leaf) и его [RSP] (адрес возврата) => непосредственный вызывающий.
import struct, collections, sys, json
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
print('профиль %s: сэмплов=%d wait=%d выровнено=%d' % (PROF, ns, wcnt, len(pairs)))

owner = collections.Counter()
leaf = collections.Counter()
chain_c = collections.Counter()
for (i, k) in pairs:
    # цепочка назад: до 6 exe-сэмплов
    ch = []
    for j in range(i - 1, max(-1, i - 9), -1):
        f = exe_fn(rips[j])
        if f:
            ch.append((j, f, rets[j] if j < nret else 0))
        if len(ch) >= 4:
            break
    if not ch:
        owner['<?>'] += 1
        continue
    j, f, ret = ch[0]
    caller = exe_fn(ret)
    owner[caller or ('ret:' + (exe_data(ret) or ('raw_%x' % ret)))] += 1
    leaf[f] += 1
    chain_c[' <- '.join(x[1] for x in ch)] += 1

tot = len(pairs)
print('\n=== НЕПОСРЕДСТВЕННЫЙ ВЫЗЫВАЮЩИЙ (по [RSP] последнего exe-сэмпла перед ожиданием) ===')
for o, c in owner.most_common(30):
    print('  %5d (%5.1f%%)  %s' % (c, 100.0 * c / tot, o))

print('\n=== LEAF exe-сэмпл перед ожиданием ===')
for o, c in leaf.most_common(15):
    print('  %5d (%5.1f%%)  %s' % (c, 100.0 * c / tot, o))

named = sum(c for o, c in owner.items() if o and not o.startswith('ret:') and o != '<?>')
print('\nназвано поимённо (вызывающий в exe): %d из %d (%.1f%%)' % (named, tot, 100.0 * named / tot))

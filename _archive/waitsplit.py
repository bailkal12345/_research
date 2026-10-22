# -*- coding: utf-8 -*-
# Слот A: полная раскладка wait-записей prof_512222984 (762 шт, 5 слов: rip + 4 кадра).
# Цель: назвать владельцев >=50% ожиданий поимённо (RVA + PDB/Ghidra-имя).
import struct, collections, sys
sys.stdout.reconfigure(encoding='utf-8')

TICKPROF = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi\Plugins\_backup\TickProf'
import profanalyze as pa
import profnamed as pn

TXT = 0x391AA6E
mods, bases = pa.load_modules(TICKPROF + r'\prof_512222984.modules.txt')
ghidra, gstarts = pn.load_ghidra_names()
namer = pn.Namer(ghidra, gstarts)


def loc(a):
    if a is None:
        return '?'
    short, off, _ = pa.mod_of(a, mods, bases)
    if short == 'ShooterGameServer.exe':
        if off >= TXT:
            return 'exe@Data+%x' % off
        return 'exe:0x%X %s' % (off, namer.name(off) or 'sub_%X' % off)
    if short:
        return '%s+%x' % (short, off)
    return 'raw_%x' % a


wdata = open(TICKPROF + r'\prof_512222984.wait', 'rb').read()
wcnt = struct.unpack_from('<Q', wdata, 0)[0]
words = struct.unpack_from('<%dQ' % (wcnt * 5), wdata, 8)
print('записей: %d' % wcnt)

# 1) syscall-классификация rip
rip_c = collections.Counter()
chains = {}  # raw rip -> counter(полн 4-словных цепочек)
for i in range(wcnt):
    rip, w1, w2, w3, w4 = words[i * 5:i * 5 + 5]
    short, off, _ = pa.mod_of(rip, mods, bases)
    rip_c['Zw*+0x%x' % off if short == 'ntdll.dll' else loc(rip)] += 1
    chain = tuple(loc(w) for w in (w1, w2, w3, w4))
    chains.setdefault(rip, collections.Counter())[chain] += 1

by_rip = collections.defaultdict(list)  # имя -> raw rip
for rip in chains:
    short, off, _ = pa.mod_of(rip, mods, bases)
    nm = 'Zw*+0x%x' % off if short == 'ntdll.dll' else loc(rip)
    by_rip[nm].append(rip)

for ripn, c in rip_c.most_common():
    print('\n=== rip %s : %d записей ===' % (ripn, c))
    cc = collections.Counter()
    for k in by_rip[ripn]:
        cc.update(chains[k])
    shown = 0
    for ch, n in cc.most_common(12):
        print('  %5d (%4.1f%%) | %s' % (n, 100.0 * n / c, ' <- '.join(ch)))
        shown += n
    if c - shown:
        print('  ... прочие цепочки: %d' % (c - shown))

# -*- coding: utf-8 -*-
# Слот B (v3): кто вызывает ServerOctreeOverlapActors в ПРОФИЛЕ ФАЗЫ.
# Метод: для сэмплов внутри ServerOctreeOverlapActors смотрим [RSP] (ret) -
# это адрес возврата, т.е. вызывающая функция exe.
import struct, collections, sys, os
sys.path.insert(0, r'C:\Dev\_research')
sys.stdout.reconfigure(encoding='utf-8')
import profanalyze as pa
import profnamed as pn

TXT = 0x391AA6E
PLUG = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi\Plugins'
ACTIVE = os.path.join(PLUG, 'TickProf')
BACK = os.path.join(PLUG, '_backup', 'TickProf')
ghidra, gstarts = pn.load_ghidra_names()
namer = pn.Namer(ghidra, gstarts)
OCT = 0x12871E0  # ServerOctreeOverlapActors


def dir_for(prof):
    return ACTIVE if os.path.exists(os.path.join(ACTIVE, 'prof_%s.wait' % prof)) else BACK


def run(prof, tag):
    D0 = dir_for(prof)
    mods, bases = pa.load_modules(os.path.join(D0, 'prof_%s.modules.txt' % prof))
    bd = open(os.path.join(D0, 'prof_%s.bin' % prof), 'rb').read()
    rd = open(os.path.join(D0, 'prof_%s.ret' % prof), 'rb').read()
    ns = len(bd) // 8
    rips = struct.unpack_from('<%dQ' % ns, bd, 0)
    nret = len(rd) // 8
    rets = struct.unpack_from('<%dQ' % nret, rd, 0)

    def exefn(a):
        s, o, _ = pa.mod_of(a, mods, bases)
        if s == 'ShooterGameServer.exe' and o < TXT:
            return namer.name(o) or ('sub_%X' % o)
        return None

    callers = collections.Counter()
    tot = 0
    for i, r in enumerate(rips):
        s, o, _ = pa.mod_of(r, mods, bases)
        if s != 'ShooterGameServer.exe' or o < OCT or o >= OCT + 1935:
            continue
        tot += 1
        if i < nret:
            callers[exefn(rets[i]) or '<non-exe>'] += 1
    print('\n##### %s (prof %s) #####' % (tag, prof))
    print('  сэмплов внутри ServerOctreeOverlapActors: %d' % tot)
    for k, c in callers.most_common(12):
        print('     %5d (%4.1f%%)  %s' % (c, 100.0 * c / max(1, tot), k))
    return dict(prof=prof, in_oct=tot, callers=dict(callers.most_common(15)))


if __name__ == '__main__':
    out = []
    out.append(run('631247234', 'СЛОТ B: ФАЗА 21.10 21:57'))
    out.append(run('512222984', 'СЛОТ A: плотная база 20.10'))
    import json
    with open(r'C:\Dev\_research\slotB\octree_callers.json', 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

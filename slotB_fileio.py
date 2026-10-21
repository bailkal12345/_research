# -*- coding: utf-8 -*-
# Слот B (v4): сырые слова стека для ZwQueryDirectoryFileEx в профиле фазы -
# ищем exe-кадр (IterateDirectory/FindFiles) в 4 доступных словах.
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

prof = sys.argv[1] if len(sys.argv) > 1 else '631247234'
D0 = ACTIVE if os.path.exists(os.path.join(ACTIVE, 'prof_%s.wait' % prof)) else BACK
mods, bases = pa.load_modules(os.path.join(D0, 'prof_%s.modules.txt' % prof))
wd = open(os.path.join(D0, 'prof_%s.wait' % prof), 'rb').read()
wcnt = struct.unpack_from('<Q', wd, 0)[0]
ww = struct.unpack_from('<%dQ' % (wcnt * 5), wd, 8)


def loc(a):
    s, o, _ = pa.mod_of(a, mods, bases)
    if s == 'ShooterGameServer.exe':
        if o >= TXT:
            return 'exeDATA+0x%X' % o
        return 'exe:0x%X %s' % (o, namer.name(o) or ('sub_%X' % o))
    if s:
        return '%s+0x%x' % (s, o)
    return 'raw_%x' % a


print('=== 12 примеров wait-записей с ZwQueryDirectoryFileEx ===')
shown = 0
for i in range(wcnt):
    rip = ww[i * 5]
    s, o, _ = pa.mod_of(rip, mods, bases)
    if s != 'ntdll.dll' or o != 0x161794:
        continue
    print('  rip=%s' % loc(rip))
    for k in range(1, 5):
        print('      [%d] %s' % (k, loc(ww[i * 5 + k])))
    shown += 1
    if shown >= 12:
        break

print('\n=== какие DLL-кадры встречаются в словах стека этих ожиданий ===')
cnt = collections.Counter()
for i in range(wcnt):
    rip = ww[i * 5]
    s, o, _ = pa.mod_of(rip, mods, bases)
    if s != 'ntdll.dll' or o != 0x161794:
        continue
    for k in range(1, 5):
        s2, o2, _ = pa.mod_of(ww[i * 5 + k], mods, bases)
        cnt[loc(ww[i * 5 + k])] += 1
for k, v in cnt.most_common(18):
    print('   %5d  %s' % (v, k))

# -*- coding: utf-8 -*-
# Slot B (v7): owner of the file IO in the phase profile.
#
# Idea: ZwQueryDirectoryFileEx = FindFirstFile/FindNextFile. In the exe these calls come
# from FWindowsPlatformFile::IterateDirectory (windowsplatformfile.cpp:273/283).
# IterateDirectory is called from FindFiles / FindPluginsRecursively / UWorldComposition::Rescan.
# In the phase profile we look for exe samples next to file-IO waits - if an
# IterateDirectory/FindFiles frame is nearby, the file IO originates there.
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

# exe function ranges related to file IO
FILE_FUNCS = {
    0x1F49900: ('IterateDirectory', 623),
    0x1EBAF0: ('FindFiles', 873),
    0x1F64200: ('FindPluginsRecursively', 2968),
    0x275BF00: ('UWorldComposition::Rescan', 7617),
    0x1EBB710: ('IterateDirectory(recursive)', 0),
}

prof = sys.argv[1] if len(sys.argv) > 1 else '631247234'
D0 = ACTIVE if os.path.exists(os.path.join(ACTIVE, 'prof_%s.wait' % prof)) else BACK
mods, bases = pa.load_modules(os.path.join(D0, 'prof_%s.modules.txt' % prof))
bd = open(os.path.join(D0, 'prof_%s.bin' % prof), 'rb').read()
rd = open(os.path.join(D0, 'prof_%s.ret' % prof), 'rb').read()
wd = open(os.path.join(D0, 'prof_%s.wait' % prof), 'rb').read()
ns = len(bd) // 8
rips = struct.unpack_from('<%dQ' % ns, bd, 0)
nret = len(rd) // 8
rets = struct.unpack_from('<%dQ' % nret, rd, 0)
wcnt = struct.unpack_from('<Q', wd, 0)[0]
ww = struct.unpack_from('<%dQ' % (wcnt * 5), wd, 8)


def exer(a):
    s, o, _ = pa.mod_of(a, mods, bases)
    return o if s == 'ShooterGameServer.exe' and o < TXT else None


def fname(o):
    return namer.name(o) or ('sub_%X' % o)


def in_file_func(o):
    for base, (nm, sz) in FILE_FUNCS.items():
        if o == base or (sz and base <= o < base + sz):
            return nm
    return None


# samples inside the exe file functions
inside = collections.Counter()
for r in rips:
    o = exer(r)
    if o is None:
        continue
    f = in_file_func(o)
    if f:
        inside[f] += 1
print('=== exe samples inside file functions (profile %s) ===' % prof)
for k, v in inside.most_common():
    print('   %5d  %s' % (v, k))
if not inside:
    print('   NO sample at all in the file functions')

# who calls: for samples in IterateDirectory/FindFiles look at [RSP]
callers = collections.Counter()
for i, r in enumerate(rips):
    o = exer(r)
    if o is None:
        continue
    f = in_file_func(o)
    if not f or i >= nret:
        continue
    c = exer(rets[i])
    callers[(f, fname(c) if c is not None else '<non-exe>')] += 1
print('\n=== callers of the file functions ([RSP]) ===')
for (f, c), v in callers.most_common(15):
    print('   %5d  %-28s <- %s' % (v, f, c))

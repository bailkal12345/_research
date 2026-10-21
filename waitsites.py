# -*- coding: utf-8 -*-
# Точные call-site'ы exe в wait-стопках (профиль базы Genesis) + контекст.
import struct, bisect, collections

TICKPROF = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi\Plugins\TickProf'
import profanalyze as pa
import profnamed as pn

TXT = 0x391AA6E

pdata, pdata_starts = pn.load_pdata()
ghidra, gstarts = pn.load_ghidra_names()
namer = pn.Namer(ghidra, gstarts)
mods, bases = pa.load_modules(TICKPROF + r'\prof_512222984.modules.txt')

name = '512222984'
wdata = open(TICKPROF + r'\prof_%s.wait' % name, 'rb').read()
wcnt = struct.unpack_from('<Q', wdata, 0)[0]
words = struct.unpack_from('<%dQ' % (wcnt * 5), wdata, 8)

site = collections.Counter()      # точный адрес exe-кода в стеке -> счёт
rip_cnt = collections.Counter()
for i in range(wcnt):
    w = words[i * 5:(i + 1) * 5]
    rip = w[0]
    rcls = pa.mod_of(rip, mods, bases)
    if rcls[0] and 'kernelbase' == rcls[0].lower():
        rip_cnt['KERNELBASE+%x' % rcls[1]] += 1
    for sv in w[1:]:
        scls = pa.mod_of(sv, mods, bases)
        if scls[0] == 'ShooterGameServer.exe' and scls[1] < TXT:
            site[scls[1]] += 1
            break

print('=== rip-сайты (должен быть KERNELBASE WaitForSingleObjectEx+0xaf):')
for k, v in rip_cnt.most_common(6):
    print('   %5d %s' % (v, k))
print()
print('=== точные exe-адреса в 4 верхних словах RSP:')
for k, v in site.most_common(25):
    nm = namer.name(k) or ('sub_%X' % k)
    print('   %5d  rva 0x%X  %s' % (v, k, nm))

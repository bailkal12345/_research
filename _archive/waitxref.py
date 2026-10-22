# -*- coding: utf-8 -*-
# Слот A: (1) поиск владельца data-объекта exe@Data+0x491c6b0 через rip-rel xref в .text;
#        (2) классификация 624 ZwWaitForSingleObject по call-site владельца.
import struct, collections, sys
sys.stdout.reconfigure(encoding='utf-8')

TICKPROF = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi\Plugins\_backup\TickProf'
import profanalyze as pa
import profnamed as pn

EXE = pn.EXE
TXT = 0x391AA6E
IMAGEBASE = 0x140000000

mods, bases = pa.load_modules(TICKPROF + r'\prof_512222984.modules.txt')
ghidra, gstarts = pn.load_ghidra_names()
namer = pn.Namer(ghidra, gstarts)

D = open(EXE, 'rb').read()
pe = struct.unpack_from('<I', D, 0x3C)[0]
nsec = struct.unpack_from('<H', D, pe + 6)[0]
opt_size = struct.unpack_from('<H', D, pe + 20)[0]
so = pe + 24 + opt_size
secs = []
for i in range(nsec):
    s = so + i * 40
    nm = D[s:s + 8].split(b'\0')[0].decode('ascii', 'replace')
    vsize = struct.unpack_from('<I', D, s + 8)[0]
    vaddr = struct.unpack_from('<I', D, s + 12)[0]
    rawsize = struct.unpack_from('<I', D, s + 16)[0]
    rawptr = struct.unpack_from('<I', D, s + 20)[0]
    secs.append((nm, vaddr, vsize, rawptr, rawsize))
text = [x for x in secs if x[0] == '.text'][0]
_, tva, tvs, trp, trs = text
body = D[trp:trp + min(tvs, trs)]


def func_of(rva):
    n = namer.name(rva)
    return n or ('sub_%X' % rva)


def xrefs_to(target_rva):
    """Все rip-relative ссылки на target_rva внутри .text."""
    out = []
    n = len(body)
    for i in range(n - 4):
        for L in (5, 6, 7, 8):
            if i + L > n:
                break
            disp = struct.unpack_from('<i', body, i + L - 4)[0]
            if tva + i + L + disp == target_rva:
                out.append((tva + i, L, body[i:i + L]))
    return out


TARGET = 0x491c6b0
xr = xrefs_to(TARGET)
print('=== rip-rel xref на exe@Data+0x491c6b0: %d ===' % len(xr))
own = collections.Counter()
for rva, L, bts in xr:
    own[func_of(rva)] += 1
for k, v in own.most_common(20):
    print('   %4d  %s' % (v, k))
print('примеры инструкций:')
for rva, L, bts in xr[:10]:
    print('   rva 0x%X  bytes %s  (%s)' % (rva, bts.hex(' '), func_of(rva)))

# movabs-ссылки (48 B8..BF imm64 = target+base)
abs_hits = []
for i in range(len(body) - 10):
    if body[i] in (0x48,) and 0xB8 <= body[i + 1] <= 0xBF:
        imm = struct.unpack_from('<Q', body, i + 2)[0]
        if imm == IMAGEBASE + TARGET:
            abs_hits.append(tva + i)
print('movabs-ссылок: %d' % len(abs_hits))
for rva in abs_hits[:10]:
    print('   rva 0x%X  %s' % (rva, func_of(rva)))

# также: какие exe-функции содержат адрес как аргумент? ищем в .text immediate 0x491c6b0
imm_hits = []
for i in range(len(body) - 4):
    if struct.unpack_from('<I', body, i)[0] == TARGET:
        imm_hits.append(tva + i)
print('immediate-вхождения 0x491c6b0: %d (первые)"' % len(imm_hits))
for rva in imm_hits[:15]:
    print('   rva 0x%X  %s' % (rva, func_of(rva)))

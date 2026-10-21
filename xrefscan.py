# -*- coding: utf-8 -*-
# Поиск rip-relative ссылок на целевой RVA в .text exe (исправленный).
# disp32 лежит в инструкции; next_ip = rva_диспа + 4;  target = next_ip + disp.
import struct, sys, collections, time
sys.stdout.reconfigure(encoding='utf-8')

EXE = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ShooterGameServer.exe'
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
nm, tva, tvs, trp, trs = [x for x in secs if x[0] == '.text'][0]
body = D[trp:trp + min(tvs, trs)]
n = len(body)

import profnamed as pn
ghidra, gstarts = pn.load_ghidra_names()
namer = pn.Namer(ghidra, gstarts)


def func_of(rva):
    return namer.name(rva) or ('sub_%X' % rva)


def find_riprel(target_rva):
    """Позиции disp32 (байтовые смещения), дающие ссылку на target_rva."""
    hits = []
    for shift in (0, 1, 2, 3):
        lim = ((n - shift) // 4) * 4
        if lim <= 0:
            continue
        mv = memoryview(body)[shift:shift + lim].cast('i')
        exp = target_rva - (tva + shift + 4)
        k = 0
        for v in mv:
            if v == exp:
                hits.append(shift + 4 * k)
            exp -= 4
            k += 1
    return hits


def modrm_ok(disp_off):
    """ModRM с mod=00, rm=101 (rip-relative) стоит за 1 или 2 байта до disp."""
    for back in (1, 2):
        j = disp_off - back
        if j < 0:
            continue
        if (body[j] & 0xC7) == 0x05:
            return back
    return 0


if __name__ == '__main__':
    for T in [int(x, 16) for x in sys.argv[1:]] or [0x491c6b0]:
        t0 = time.time()
        print('\n######## TARGET RVA 0x%X ########' % T)
        cand = find_riprel(T)
        print('кандидатов disp32: %d (%.1f c)' % (len(cand), time.time() - t0))
        real = []
        for i in cand:
            b = modrm_ok(i)
            if b:
                real.append((i - b, body[i - b:i + 4]))
        print('с ModRM rip-relative: %d' % len(real))
        own = collections.Counter(func_of(r) for r, b in real)
        for k, v in own.most_common(15):
            print('   %4d  %s' % (v, k))
        for r, b in real[:20]:
            print('     rva 0x%X bytes=%s  (%s)' % (r, b.hex(' '), func_of(r)))

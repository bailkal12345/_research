# -*- coding: utf-8 -*-
# Кто ссылается на exe-данные 0x491C6B0 (&GNatives) из .text: разбор ModRM/REX.
import struct, sys, collections
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
    """disp32-позиции, дающие rip-relative ссылку на target."""
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


def decode_site(dpos):
    """Попытка восстановить начало инструкции и ModRM для disp-позиции dpos."""
    # вариант A: ModRM в dpos-1, опционально REX в dpos-2
    for back in (1, 2):
        j = dpos - back
        if j < 1:
            continue
        modrm = body[j]
        if (modrm & 0xC7) == 0x05:  # mod=00, rm=101 => rip-relative
            start = j - 1
            if back == 2:
                # j должен быть ModRM, j-1 = REX (0x40..0x4F)
                if not (0x40 <= body[j - 1] <= 0x4F):
                    continue
            else:
                # ModRM сразу после однобайтового opcode: 8B/89/8D/03/2B/33/39/3B/FF/63/0F
                op = body[j - 1]
                if op not in (0x8B, 0x89, 0x8D, 0x03, 0x2B, 0x33, 0x39, 0x3B, 0xFF, 0x63, 0x8A):
                    continue
            return start, body[j]
    return None, None


for T in [int(x, 16) for x in sys.argv[1:]] or [0x491C6B0]:
    print('\n######## TARGET RVA 0x%X ########' % T)
    cands = find_riprel(T)
    print('disp32-кандидатов: %d' % len(cands))
    byfn = collections.Counter()
    sites = []
    for d in cands:
        st, modrm = decode_site(d)
        if st is None:
            continue
        byfn[func_of(tva + st)] += 1
        sites.append((tva + st, tva + d))
    print('декодировано как ModRM/rm=101: %d' % len(sites))
    for k, v in byfn.most_common(25):
        print('   %4d  %s' % (v, k))

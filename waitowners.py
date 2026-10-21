# -*- coding: utf-8 -*-
# Слот A: кто владелец массированного wait-кластера (exe@Data+0x491c6b0 в стеке).
# Строю xref-скан кода .text на этот data-адрес (rip-rel) и сравнение с пустым профилем.
import struct, collections, sys
sys.stdout.reconfigure(encoding='utf-8')

TICKPROF = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi\Plugins\_backup\TickProf'
import profanalyze as pa
import profnamed as pn

EXE = pn.EXE
TXT = 0x391AA6E
mods, bases = pa.load_modules(TICKPROF + r'\prof_512222984.modules.txt')
ghidra, gstarts = pn.load_ghidra_names()
namer = pn.Namer(ghidra, gstarts)


def loc(a):
    short, off, _ = pa.mod_of(a, mods, bases)
    if short == 'ShooterGameServer.exe':
        if off >= TXT:
            return 'exe@Data+%x' % off
        return 'exe:0x%X %s' % (off, namer.name(off) or 'sub_%X' % off)
    if short:
        return '%s+%x' % (short, off)
    return 'raw_%x' % a

# --- секции exe+ чтение байтов ---
from struct import unpack_from
D = open(EXE, 'rb').read()
pe = unpack_from('<I', D, 0x3C)[0]
nsec = unpack_from('<H', D, pe + 6)[0]
opt = pe + 24
opt_size = unpack_from('<H', D, pe + 20)[0]
secs = []
so = opt + opt_size
for i in range(nsec):
    s = so + i * 40
    vaddr = unpack_from('<I', D, s + 12)[0]
    vsize = unpack_from('<I', D, s + 8)[0]
    rawsize = unpack_from('<I', D, s + 16)[0]
    rawptr = unpack_from('<I', D, s + 20)[0]
    nm = D[s + 1:s + 8].split(b'\0')[0].decode('ascii', 'replace')
    secs.append((nm, vaddr, vsize, rawptr, rawsize))

# --- 1) xrefs на exe@Data+0x491c6b0 ---
TARGET = 0x491c6b0
hits = collections.Counter()
first_far = []
for nm, va, vs, rp, rs in secs:
    if nm not in ('.text',):
        continue
    body = D[rp:rp + min(vs, rs)]
    for i in range(len(body) - 8):
        # rip-rel префиксы 48 8D /CC/2D/05..., 48 8B, 4C 8D, 8B 05...
        if 0x48 <= body[i] <= 0x4F and body[i + 1] == 0x8D:
            off = i + 2
            # disp в конце 4-байт: ins len 7 (модов=0 typical '48 8D 0D disp')
            pass
    # generic: скан по всем позициям, disp32 имя target через (addr_next + disp)
    for i in range(len(body) - 4):
        disp = unpack_from('<i', body, i)[0]
        instr_end = va + i + 4
        if 0 <= instr_end + disp < 0x3A00000 and instr_end + disp == TARGET + 0x140000000:
            pass
# точный проход с декодированием только rip-rel LEA/MOV-опкодов
for nm, va, vs, rp, rs in secs:
    if nm != '.text':
        continue
    body = D[rp:rp + min(vs, rs)]
    n = len(body)
    i = 0
    while i < n - 8:
        b0 = body[i]
        # интересуемся 7-байт: [REX][0F..?]. —通用: (REX 8Displacement) 48/4C 8B/8D + ModRM c mod=00 rm=101
        if b0 in (0x48, 0x4C) and body[i + 1] in (0x8B, 0x8D) and body[i + 2] in (0x05, 0x0D, 0x15, 0x1D, 0x25, 0x2D, 0x35):
            disp = unpack_from('<i', body, i + 3)[0]
            tgt = va + i + 7 + disp
            if tgt == TARGET:
                hits['lea	mov_[%s]' % body[i + 2]] += 1
                first_far.append((va + i, body[i + 1], body[i + 2]))
            i += 7
            continue
        i += 1

print('xref на exe@Data+0x491c6b0:')
for (addr, op, modrm), c in collections.Counter(first_far).most_common(20):
    print('   rva 0x%X %s  insn=48 %s(rip) %s -> %s' % (
        addr, ('%d шт' % c), hex(op), hex(modrm), loc(addr + 7)))

# owners функция xref
own = collections.Counter()
for (addr, op, modrm), c in collections.Counter(first_far).items():
    own[loc(addr)] += c
print('функция-владелец xref:')
for k, v in own.most_common(10):
    print('   %5d %s' % (v, k))

# --- 2) сравнение с пустым профилем 298529359 ---
for prof in ('298529359', '301269000'):
    wdata = open(TICKPROF + r'\prof_%s.wait' % prof, 'rb').read()
    wc = struct.unpack_from('<Q', wdata, 0)[0]
    ws = struct.unpack_from('<%dQ' % (wc * 5), wdata, 8)
    fam = collections.Counter()
    for i in range(wc):
        rip, w2, w3, w4, _ = ws[i * 5:i * 5 + 5]
        short, off, _ = pa.mod_of(rip, mods, bases)
        if short != 'ntdll.dll':
            continue
        sig = loc(w3) if w3 else '0'
        fam[(('kernel', loc(w2) if w2 else '0'), sig)] += 1
    print('\n=== профиль %s (ntdll-wait %d из %d) w2/w3-семейства ===' % (prof, sum(sp[1] for sp in fam.most_common()[:0] or []), wc))
    for k, n in fam.most_common(10):
        print('   %5d (%4.1f%%) w2=%s w3=%s' % (n, 100.0 * n / wc, k[0], k[1]))

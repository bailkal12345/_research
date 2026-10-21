# -*- coding: utf-8 -*-
# Слот B (v6): vtable-слот FFileManagerGeneric::FindFiles -> вызовы call [reg+off].
import struct, collections, sys
sys.path.insert(0, r'C:\Dev\_research')
sys.stdout.reconfigure(encoding='utf-8')
import callsites_all as cs
import pdbsym

IMAGEBASE = 0x140000000
EXE = cs.EXE
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


def r2o(rva):
    for nm, va, vs, rp, rs in secs:
        if va <= rva < va + max(vs, rs):
            return rp + (rva - va)
    return None


FIND_FILES = IMAGEBASE + 0x1EBAF0
ITERDIR = IMAGEBASE + 0x1F49900
pat = struct.pack('<Q', FIND_FILES)
print('=== указатели на FindFiles (0x%X) по всему образу ===' % FIND_FILES)
hits = []
i = 0
while True:
    j = D.find(pat, i)
    if j < 0:
        break
    # RVA: определить секцию
    rva = None
    for nm, va, vs, rp, rs in secs:
        if rp <= j < rp + rs:
            rva = va + (j - rp)
            sec = nm
    hits.append((rva, sec))
    i = j + 1
for h in hits:
    print('   RVA 0x%X  секция %s' % h)

# Для каждой позиции: ищем базу vtable (шаг назад по цепочке qword'ов) и слот
print('\n=== слоты и вызовы ===')
text = [x for x in secs if x[0] == '.text'][0]
nm, tva, tvs, trp, trs = text
tbody = D[trp:trp + min(tvs, trs)]

for rva, sec in hits:
    off = r2o(rva)
    # база vtable: идём назад, пока qword похож на VA функции exe
    base = off
    for k in range(1, 40):
        q = struct.unpack_from('<Q', D, off - k * 8)[0]
        if not (IMAGEBASE <= q < IMAGEBASE + 0x4D00000):
            base = off - (k - 1) * 8
            break
    slot = off - base
    print('\n  FindFiles в RVA 0x%X (%s); база vtable ~0x%X, слот=0x%X' % (rva, sec, base, slot))
    # call [reg+slot]: FF 90+reg 04 disp32
    found = []
    for i2 in range(len(tbody) - 6):
        if tbody[i2] == 0xFF and 0x90 <= tbody[i2 + 1] <= 0x97:
            disp = struct.unpack_from('<i', tbody, i2 + 2)[0]
            if disp == slot:
                site = tva + i2
                fs, fname = cs.func_start(site)
                f_, l_ = pdbsym.resolve_lines(site + 6)
                src = ('%s:%s' % (f_.replace('d:\\ase\\engine\\source\\', '').replace('\\', '/'), l_)) if f_ else '?'
                found.append((site, fname, src))
    print('     call [reg+0x%X]: %d' % (slot, len(found)))
    for site, fname, src in found[:25]:
        print('        0x%X  %-40s %s' % (site, fname or '?', src))

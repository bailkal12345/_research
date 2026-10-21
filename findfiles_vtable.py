# -*- coding: utf-8 -*-
# Слот B (v5): кто вызывает FFileManagerGeneric::FindFiles (vtable) в exe.
# Ищем: 1) позицию FindFiles в .rdata (vtable), 2) call [reg+off] с этим смещением.
import struct, collections, sys
sys.path.insert(0, r'C:\Dev\_research')
sys.stdout.reconfigure(encoding='utf-8')
import callsites_all as cs
import pdbsym

IMAGEBASE = 0x140000000
D = open(cs.EXE, 'rb').read()
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


FIND_FILES_VA = IMAGEBASE + 0x1EBAF0
ITERDIR_VA = IMAGEBASE + 0x1F49900

print('=== поиск указателя на FindFiles (0x%X) в .rdata ===' % FIND_FILES_VA)
target = struct.pack('<Q', FIND_FILES_VA)
rdata = [x for x in secs if x[0] == '.rdata'][0]
nm, va, vs, rp, rs = rdata
body = D[rp:rp + min(vs, rs)]
hits = []
i = 0
while True:
    j = body.find(target, i)
    if j < 0:
        break
    hits.append(va + j)
    i = j + 1
print('  найдено в .rdata: %s' % ['0x%X' % h for h in hits])

for h in hits:
    # окно вокруг: соседние qword'ы
    off = h - va
    lo = max(0, (off // 8) - 10)
    print('\n  vtable-кандидат @0x%X, окно:' % h)
    for k in range(lo, lo + 24):
        q = struct.unpack_from('<Q', body, k * 8)[0]
        if IMAGEBASE <= q < IMAGEBASE + 0x4D00000:
            fsn, fs = cs.func_start(q - IMAGEBASE)
            mark = ' <== FindFiles' if q == FIND_FILES_VA else ''
            print('     slot 0x%X: 0x%X  %s%s' % (k * 8, q, fsn or '?', mark))
        else:
            print('     slot 0x%X: 0x%X' % (k * 8, q))

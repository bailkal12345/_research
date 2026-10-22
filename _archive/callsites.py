# -*- coding: utf-8 -*-
# Байты exe по RVA прямо из файла; декодируем call-инструкции возле wait-сайтов,
# резолвим цели по TSV-именам (Ghidra/PDB).
import struct, bisect

EXE = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ShooterGameServer.exe'
TSV = r'C:\Dev\_research\ghidra_funcs_v361.tsv'

with open(EXE, 'rb') as f:
    data = f.read()
pe_off = struct.unpack_from('<I', data, 0x3C)[0]
coff = pe_off + 4
nsec = struct.unpack_from('<H', data, coff + 2)[0]
opt_size = struct.unpack_from('<H', data, coff + 16)[0]
sec_off = coff + 20 + opt_size
secs = []
for i in range(nsec):
    s = sec_off + i * 40
    vsize = struct.unpack_from('<I', data, s + 8)[0]
    vaddr = struct.unpack_from('<I', data, s + 12)[0]
    rawsize = struct.unpack_from('<I', data, s + 16)[0]
    rawptr = struct.unpack_from('<I', data, s + 20)[0]
    secs.append((vaddr, max(vsize, rawsize), rawptr))

def rva2off(rva):
    for vaddr, vsz, rawptr in secs:
        if vaddr <= rva < vaddr + vsz:
            return rawptr + (rva - vaddr)
    return None

def read(rva, n):
    o = rva2off(rva)
    return data[o:o + n]

names = []
with open(TSV, 'r', encoding='utf-8', errors='replace') as f:
    for line in f:
        p = line.rstrip('\n').split('\t')
        if len(p) == 3:
            try:
                names.append((int(p[0], 16), int(p[2]), p[1]))
            except ValueError:
                pass
names.sort()
starts = [x[0] for x in names]

def name_of(rva):
    i = bisect.bisect_right(starts, rva) - 1
    if i >= 0:
        s, sz, nm = names[i]
        if rva < s + sz:
            return '%s%s' % (nm, ('+%x' % (rva - s)) if rva != s else '')
    return None

def scan_calls(rva, n, label=''):
    b = read(rva, n)
    print('--- %s байты 0x%X..+0x%X' % (label, rva, n))
    print('    hex: ' + b.hex())
    for i in range(len(b) - 5):
        if b[i] == 0xE8 and b[i + 5] in range(0, 256):
            rel = struct.unpack_from('<i', b, i + 1)[0]
            tgt = rva + i + 5 + rel
            nm = name_of(tgt)
            if nm:
                print('   site 0x%X call rel32 -> 0x%X  %s' % (rva + i, tgt, nm))
        elif b[i] == 0xFF and b[i + 1] == 0x15:
            disp = struct.unpack_from('<i', b, i + 2)[0]
            tgt = rva + i + 6 + disp
            print('   site 0x%X call [rip+0x%x] -> IAT/data 0x%X' % (rva + i, disp, tgt))

if __name__ == '__main__':
    scan_calls(0x2478240, 139, 'CallRemoteFunction целиком')
    print()
    scan_calls(0x1EA8900, 0x100, 'ProcessTasksNamedThread у wait-сайта')

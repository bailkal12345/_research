# -*- coding: utf-8 -*-
# Опознать функцию по RIP-относительным адресам строк: дизассм окна call-участка
# крэша (0x2C290..0x2CA6A и 0x263A0..0x263C0), декод .rdata-строк, встречающихся в LEA.
import re
import struct
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

dll = r'C:\Dev\ARK-Server-Plugins\TickProf\TickProf\build\Release\TickProf.dll'
data = open(dll, 'rb').read()

pe = struct.unpack('<I', data[0x3C:0x40])[0]
nsec = struct.unpack('<H', data[pe + 6:pe + 8])[0]
optsize = struct.unpack('<H', data[pe + 20:pe + 22])[0]
sec0 = pe + 24 + optsize
secs = []
for i in range(nsec):
    o = sec0 + 40 * i
    name = data[o:o + 8].split(b'\0', 1)[0].decode('ascii', 'replace')
    vsize, vaddr, rawsize, rawptr = struct.unpack('<IIII', data[o + 8:o + 24])
    secs.append((name, vaddr, vsize, rawptr, rawsize))


def rva2off(rva):
    for name, vaddr, vsize, rawptr, rawsize in secs:
        if vaddr <= rva < vaddr + vsize:
            if rawptr and (rva - vaddr) < rawsize:
                return rawptr + (rva - vaddr)
            return None
    return None


def sec_of(rva):
    for name, vaddr, vsize, rawptr, rawsize in secs:
        if vaddr <= rva < vaddr + vsize:
            return name
    return None


def rdstr(rva, limit=120):
    off = rva2off(rva)
    if off is None:
        return None
    ends = data.find(b'\x00', off, off + limit)
    b = data[off:ends if ends > 0 else off + limit]
    try:
        s = b.decode('utf-8')
        return s if sum(1 for c in s if c.isprintable()) > max(2, len(s)//4) else None
    except UnicodeDecodeError:
        return None


md = Cs(CS_ARCH_X86, CS_MODE_64)
for lo, hi, tag in ((0x2C290, 0x2CA6A, 'ВЛАДЕЛЕЦ КРЭША #2'), (0x26160, 0x261C8, 'деструктор')):
    print('======== %s: 0x%X..0x%X ========' % (tag, lo, hi))
    code = data[rva2off(lo):rva2off(lo) + (hi - lo)]
    STR_RE = re.compile(r'\[rip \+ (0x[0-9a-f]+)\]')
    for ins in md.disasm(code, lo):
        m = re.search(r'rip \+ (0x[0-9a-f]+)', ins.op_str)
        s = None
        if m:
            addr = ins.address + ins.size + int(m.group(1), 16)
            sc = sec_of(addr)
            if sc in ('.rdata', '.data'):
                s = rdstr(addr)
        extra = ('   | str@0x%X %r' % (addr, s)) if s else ''
        print('%08x %-8s %s%s' % (ins.address, ins.mnemonic, ins.op_str, extra))

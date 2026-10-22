# -*- coding: utf-8 -*-
# Полный дизассм функции, содержащей RVA крэша, + поиск E8/E9-вызовов её старта.
import struct, sys
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


target = int(sys.argv[1], 16) if len(sys.argv) > 1 else 0x26166

# намеренно: границы функции через .pdata (RUNTIME_FUNCTION 12 байт)
pdata_off, pdata_size = None, None
for name, vaddr, vsize, rawptr, rawsize in secs:
    if name == '.pdata':
        pdata_off = rawptr
        pdata_size = rawsize
bounds = None
for i in range(0, pdata_size, 12):
    beg, end, unw = struct.unpack('<III', data[pdata_off + i:pdata_off + i + 12])
    if beg <= target < end:
        bounds = (beg, end)
        print('.pdata: функция 0x%X .. 0x%X' % (beg, end))
        break
if not bounds:
    bounds = (target - 0x40, target + 0x60)
    print('(.pdata не дал границ, окно %X..%X)' % bounds)

beg, end = bounds
md = Cs(CS_ARCH_X86, CS_MODE_64)
code = data[rva2off(beg):rva2off(beg) + (end - beg)]
for ins in md.disasm(code, beg):
    mark = '  <<<< КРЭШ+0x%X' % (target - ins.address) if ins.address <= target < ins.address + ins.size else ''
    print('%08x %-9s %s%s' % (ins.address, ins.mnemonic, ins.op_str, mark))

# поиск прямых вызовов/джампов на beg (E8/E9 rel32)
print('==== прямые переходы на 0x%X ====' % beg)
t = 0x1000
body = data[0x400:0x400 + 0x3ED2E]  # .text/raw
i = 0
callers = []
while i < len(body) - 5:
    if body[i] in (0xE8, 0xE9):
        rel = struct.unpack('<i', body[i + 1:i + 5])[0]
        src_rva = 0x1000 + i
        dst = src_rva + 5 + rel
        if dst == beg:
            callers.append(src_rva)
            print('  от 0x%X (%s)' % (src_rva, 'call' if body[i] == 0xE8 else 'jmp'))
    i += 1

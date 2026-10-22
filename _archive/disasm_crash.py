# -*- coding: utf-8 -*-
# Разбор участка TickProf.dll около RVA крэша: RVAT->file offset, дизассм.
import struct, sys
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

dll = r'C:\Dev\ARK-Server-Plugins\TickProf\TickProf\build\Release\TickProf.dll'
data = open(dll, 'rb').read()

pe = struct.unpack('<I', data[0x3C:0x40])[0]
machine = struct.unpack('<H', data[pe + 4:pe + 6])[0]
nsec = struct.unpack('<H', data[pe + 6:pe + 8])[0]
optsize = struct.unpack('<H', data[pe + 20:pe + 22])[0]
opt = pe + 24
sec0 = opt + optsize
print('machine=0x%X sections=%d opt=%d' % (machine, nsec, optsize))

secs = []
for i in range(nsec):
    o = sec0 + 40 * i
    name = data[o:o + 8].split(b'\0', 1)[0].decode('ascii', 'replace')
    vsize, vaddr, rawsize, rawptr = struct.unpack('<IIII', data[o + 8:o + 24])
    secs.append((name, vaddr, vsize, rawptr, rawsize))


def rva2off(rva):
    for name, vaddr, vsize, rawptr, rawsize in secs:
        if vaddr <= rva < vaddr + vsize:
            if rawptr and rva - vaddr < rawsize:
                return rawptr + (rva - vaddr)
            return None
    return None


for name, vaddr, vsize, rawptr, rawsize in secs:
    print('%-8s vaddr=%#08x vsize=%#x raw=%#x/%#x' % (name, vaddr, vsize, rawptr, rawsize))

target = int(sys.argv[1], 16) if len(sys.argv) > 1 else 0x26166
base_of_file = min(s[1] for s in secs if s[1] > 0)  # первый сек-виртуальный адрес
IMAGEBASE_IN_FILE = base_of_file  # RVA в файле vs офсет в файле одинакова странность
# ВАЖНО: WER-офсет = fault_addr - module_base => RVA (образ загрузки).
# Дизассм окна [-0x60 .. +0x20].
lo, hi = target - 0x60, target + 0x20
off0 = rva2off(lo)
code = data[off0:off0 + (hi - lo)]
md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = False
for ins in md.disasm(code, lo):
    mark = '  <<<< КРЭШ' if ins.address <= target < ins.address + ins.size else ''
    txt = '%08x  %-8s %s%s' % (ins.address, ins.mnemonic, ins.op_str, mark)
    b = ' '.join('%02x' % x for x in ins.bytes)
    print('%-36s | %s' % (b, txt))

# -*- coding: utf-8 -*-
"""Проверяем PE debug directory образа и заголовок MSF (.pdb)."""
import ctypes as C
import struct
import uuid

print("ptrsize:", C.sizeof(C.c_void_p), "ulong:", C.sizeof(C.c_ulong))

image = r"C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ShooterGameServer.exe"
pdb = image.rsplit(".", 1)[0] + ".pdb"

with open(image, "rb") as f:
    data = f.read()

pe_off = struct.unpack_from("<I", data, 0x3C)[0]
assert data[pe_off:pe_off + 4] == b"PE\0\0"
machine, nsec = struct.unpack_from("<HH", data, pe_off + 4)
opt_size = struct.unpack_from("<H", data, pe_off + 20)[0]
opt = pe_off + 24
magic = struct.unpack_from("<H", data, opt)[0]
print("machine=%#x sections=%d optmagic=%#x" % (machine, nsec, magic))
dd_off = opt + (112 if magic == 0x20B else 96)
num_dd = struct.unpack_from("<I", data, dd_off - 4)[0]
print("num data dirs:", num_dd)

# data dir entry 6 = Debug
dbg_rva, dbg_size = struct.unpack_from("<II", data, dd_off + 6 * 8)
print("debug dir rva=%#x size=%d" % (dbg_rva, dbg_size))

secs = []
so = pe_off + 24 + opt_size
for i in range(nsec):
    base = so + i * 40
    name = data[base:base + 8].rstrip(b"\0").decode()
    vsize, vaddr, rsize, raddr = struct.unpack_from("<IIII", data, base + 8)
    secs.append((vaddr, vsize, raddr, rsize, name))


def rva2off(rva):
    for vaddr, vsize, raddr, rsize, name in secs:
        if vaddr <= rva < vaddr + max(vsize, rsize):
            return raddr + (rva - vaddr), name
    return None, None


if dbg_rva:
    off, sec = rva2off(dbg_rva)
    print("debug dir at file off %#x (%s)" % (off, sec))
    pos = off
    while pos < off + dbg_size:
        d_chars, d_ts, d_maj, d_min, d_type, d_size, d_addr_rva, d_raw = struct.unpack_from("<IIHHIIII", data, pos)
        print("  entry type=%d size=%d rva=%#x raw=%#x" % (d_type, d_size, d_addr_rva, d_raw))
        if d_type == 2 and d_raw:  # IMAGE_DEBUG_TYPE_CODEVIEW
            rec = data[d_raw:d_raw + d_size]
            print("    sig=%r" % rec[:4])
            if rec[:4] == b"RSDS":
                guid = uuid.UUID(bytes_le=rec[4:20])
                age = struct.unpack_from("<I", rec, 20)[0]
                pdbname = rec[24:].split(b"\0")[0].decode(errors="replace")
                print("    guid=%s age=%d pdb=%r" % (guid, age, pdbname))
        pos += 28

with open(pdb, "rb") as f:
    head = f.read(64)
print("pdb header: %r" % head[:32])
print("pdb size: %d" % __import__("os").path.getsize(pdb))
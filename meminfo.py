import sys, os
from minidump.minidumpfile import MinidumpFile

path = sys.argv[1]
addrs = [int(a, 16) for a in sys.argv[2:]]
mdf = MinidumpFile.parse(path)
mods = [(m.baseaddress, m.size, os.path.basename(str(m.name or "?"))) for m in (mdf.modules.modules if mdf.modules else [])]

def resolve(addr):
    for base, size, name in mods:
        if base <= addr < base + size:
            return f"{name}+0x{addr-base:X}"
    return None

mins = getattr(mdf, "virtual_memory_info", None) or getattr(mdf, "memory_info", None)
regions = []
if mins and getattr(mins, "infos", None):
    for inf in mins.infos:
        regions.append((inf.startaddr, inf.endaddr, inf.state, inf.protection, inf.type))
    regions.sort()
else:
    print("no meminfo stream")

def info_for(a):
    for s, e, st, pr, ty in regions:
        if s <= a < e:
            return f"region 0x{s:X}-0x{e:X} len={ (e-s)/1024:.0f}K state=0x{st:X} prot=0x{pr:X} type=0x{ty:X}"
    return "no region"

reader = mdf.get_reader()
for a in addrs:
    try:
        data = reader.read(a, 64)
        first = "; ".join(resolve(v) or f"0x{v:X}" for v in __import__("struct").unpack("<8Q", data[:64]))
    except Exception as e:
        first = f"(unreadable: {e})"
    print(f"addr 0x{a:X}: {info_for(a)}")
    print(f"   mod? {resolve(a) or '-'}")
    print(f"   first64: {first[:300]}")

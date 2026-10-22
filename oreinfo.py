import sys, os, struct
from minidump.minidumpfile import MinidumpFile

path = sys.argv[1]
targets = []
for a in sys.argv[2:]:
    if a.lower().startswith("0x"):
        targets.append(int(a, 16))
    else:
        m = __import__("re").match(r"([0-9a-fA-F]+):([0-9]+)?", a)
        # form base:delta - relative address in the region (forward/backward)
        if m:
            targets.append((m.group(1).lower(), int(m.group(2) or 0)))
        else:
            targets.append(int(a, 16))

mdf = MinidumpFile.parse(path)
# modules
try:
    mods = [(m.baseaddress, m.size, os.path.basename(str(m.name or "?"))) for m in mdf.modules.modules]
except Exception:
    mods = []

def resolve(addr):
    for base, size, name in mods:
        if base <= addr < base + size:
            return f"{name}+0x{addr-base:X}"
    return None

segs = mdf.memory_segments_64.memory_segments
ranges = []
for s in segs:
    ranges.append((s.start_virtual_address, s.start_virtual_address + s.size, s.start_virtual_address))
ranges.sort()

# classification of each target: neighboring committed ranges beyond/before, length of the contiguous commit
def scan(target):
    # find the host range
    host = None
    # form the absolute address
    base = None
    if isinstance(target, tuple):
        base = next((b for b, e, _ in ranges if b <= int(target[0], 16) < e), None)
        if base is None:
            # base as a module?
            for b, e, _ in ranges:
                pass
        if base is None:
            for mbase, msize, name in mods:
                if str(name).lower().startswith("engineswap"):
                    base = mbase + target[1]
        if base is None:
            print("can't resolve", target)
            return
    else:
        base = target

    # host range
    host = None
    for s, e, _ in ranges:
        if s <= base < e:
            host = (s, e)
            break
    # contiguous before/after
    total = 0
    if host:
        lo, hi = host[0], host[1]
        # expansion downwards
        changed = True
        while changed:
            changed = False
            for s, e, _ in ranges:
                if e == lo:
                    lo = s; changed = True
        changed = True
        while changed:
            changed = False
            for s, e, _ in ranges:
                if s == hi:
                    hi = e; changed = True
        total = hi - lo
    print(f"target 0x{base:X} host={(hex(host[0]), hex(host[1])) if host else None} "
          f"contiguous={( total/1024/1024):.1f} MiB mod={resolve(base) or '-'}")
    # read 64 bytes
    reader = mdf.get_reader()
    try:
        data = reader.read(base, 64)
        vals = struct.unpack("<8Q", data)
        print("   first64:", " ".join(resolve(v) or f"0x{v:X}" for v in vals))
    except Exception as e:
        print("   first64 unreadable:", e)

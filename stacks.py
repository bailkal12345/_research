import sys, struct, os
from collections import defaultdict
from minidump.minidumpfile import MinidumpFile

path = sys.argv[1]
mdf = MinidumpFile.parse(path)
ts = mdf.threads
mods = [(m.baseaddress, m.size, os.path.basename(str(m.name or "?"))) for m in mdf.modules.modules]

def resolve(addr):
    for base, size, name in mods:
        if base <= addr < base + size:
            return f"{name}+0x{addr-base:X}"
    return f"0x{addr:X}"

# virtual memory of the dump for stack reads
reader = mdf.get_reader()

n = 0
for t in ts.threads:
    tid = t.ThreadId
    sp = t.Stack.StartOfMemoryRange
    if sp == 0:
        continue
    # read raw stack bytes and scan for return-address-like values
    try:
        data = reader.read(sp, min(0x4000, t.Stack.EndOfMemoryRange - sp))
    except Exception as e:
        try:
            data = reader.read(sp, 0x800)
        except Exception:
            continue
    hits = []
    for off in range(0, len(data) - 8, 8):
        v = struct.unpack_from("<Q", data, off)[0]
        r = resolve(v)
        if not r.startswith("0x0") and "+" in r:
            hits.append((off, r))
    # compress: first 12 distinct frames from top
    tops = []
    seen = set()
    for off, r in hits:
        if r in seen:
            continue
        seen.add(r)
        tops.append(r)
        if len(tops) >= 14:
            break
    n += 1
    print(f"TID {tid}: SP=0x{sp:X}")
    for i, r in enumerate(tops):
        print(f"    {i} {r}")
print(f"({n} threads)")

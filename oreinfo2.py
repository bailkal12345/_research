import os, struct
from minidump.minidumpfile import MinidumpFile

mdf = MinidumpFile.parse(r"C:\Dev\_research\hung_18896.dmp")
targets = [0x35364267B80, 0x2225849DB88, 0x2225849DB70]

try:
    mods = []
    if mdf.modules and mdf.modules.modules:
        for m in mdf.modules.modules:
            mods.append((m.baseaddress, m.size, os.path.basename(str(m.name or "?"))))
except Exception:
    mods = []

def resolve(addr):
    for b, s, n in mods:
        if b <= addr < b + s:
            return f"{n}+0x{addr-b:X}"
    return None

segs = mdf.memory_segments_64.memory_segments
ranges = sorted([(s.start_virtual_address, s.size) for s in segs])
starts = [r[0] for r in ranges]

def host_of(a):
    import bisect
    i = bisect.bisect_right(starts, a) - 1
    if i >= 0:
        s, sz = ranges[i]
        if s <= a < s + sz:
            return s, sz
    return None

def contiguous(a):
    h = host_of(a)
    if not h:
        return None
    lo, hi = h
    ss = {s for s, _ in ranges}
    gz = {s: sz for s, sz in ranges}
    go = True
    while go:
        go = False
        while lo in gz and (lo - gz.get(lo - gz.get(lo, 0), -1)) != -1 and (lo - gz.get(lo, 0)) in gz:
            lo -= gz[lo]
            go = True
        if (lo - gz.get(lo, 0)) in gz:
            lo -= gz[lo]
            go = True
    go = True
    while go:
        go = False
        hi2 = hi
        while hi2 in gz and (hi2 + gz[hi2]) in gz:
            hi2 += gz[hi2]
            go = True
        hi = hi2
    return lo, hi - lo

reader = mdf.get_reader()
for a in targets:
    h = host_of(a)
    c = contiguous(a)
    print(f"target 0x{a:X} host={None if not h else (hex(h[0]), hex(h[0]+h[1]))} "
          f"contig={None if not c else (hex(c[0]), f'{c[1]/1024/1024:.1f}MiB')} mod={resolve(a) or '-'}")
    try:
        data = reader.read(a, 64)
        vals = struct.unpack("<8Q", data)
        print("  first64:", " ".join(resolve(v) or f"0x{v:X}" for v in vals))
    except Exception as e:
        print("  first64 unreadable:", e)

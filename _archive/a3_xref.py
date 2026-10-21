import struct, sqlite3, bisect, sys

p = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ShooterGameServer.exe'
d = open(p, 'rb').read()
TEXT_RVA = 0x1000; TEXT_RA = 0x400; TEXT_SZ = 0x3919c00
seg = d[TEXT_RA:TEXT_RA + TEXT_SZ]

con = sqlite3.connect(r'C:\Dev\_research\v361.sqlite')
rows = sorted(set(con.execute("select rva,name,size from fn where rva is not null and size>0").fetchall()))
addrs = [r[0] for r in rows]
info = {r[0]: (r[1], r[2]) for r in rows}

def lookup(rva):
    i = bisect.bisect_right(addrs, rva) - 1
    if i < 0: return None
    base = addrs[i]
    n, s = info[base]
    if rva < base + s: return (base, n, rva - base)
    return None

targets = {}
for a in sys.argv[1:]:
    targets[int(a, 16)] = None

# build reverse: for each call site found, which target
res = {t: [] for t in targets}
for i in range(len(seg) - 5):
    if seg[i] != 0xE8: continue
    rel = struct.unpack_from('<i', seg, i + 1)[0]
    t = TEXT_RVA + i + 5 + rel
    if t in res:
        res[t].append(TEXT_RVA + i)

for t in sys.argv[1:]:
    t = int(t, 16)
    r = lookup(t)
    print("=== target 0x%x %s" % (t, r[1] if r else '?'))
    cs = res[t]
    if not cs:
        print("   (no direct call sites)")
    for c in sorted(cs):
        q = lookup(c)
        if q:
            print("   0x%x  in 0x%x %s +0x%x" % (c, q[0], q[1], q[2]))
        else:
            print("   0x%x  in ??" % c)

import struct, sys
sys.path.insert(0, r"C:\Dev\_research")
import dumpinfo as D
p = r"C:\asmdata\Servers\Server1\ShooterGame\Saved\Logs\Dump-490729840.dmp"
d = open(p, "rb").read()
n = D.u32(d, 8); dr = D.u32(d, 12)
st = {}
for i in range(n):
    o = dr + i*12
    st.setdefault(D.u32(d,o), (D.u32(d,o+4), D.u32(d,o+8)))
print("потоки каталогов:", {D.STREAM.get(k,k): hex(v[1]) for k,v in st.items()})
addr = None
if 6 in st:
    r = st[6][1]; addr = D.u64(d, r+24); print("адрес исключения 0x%X" % addr)
if 4 in st:
    r = st[4][1]; cnt = D.u32(d, r)
    print("модулей:", cnt)
    mods=[]
    for i in range(cnt):
        o = r + 4 + i*108
        base, size, nr = D.u64(d,o), D.u32(d,o+8), D.u32(d,o+20)
        ln = D.u32(d, nr); nm = d[nr+4:nr+4+ln].decode("utf-16-le","replace")
        mods.append((base, base+size, nm))
    for b0,b1,nm in mods: print("  0x%012X-%012X %s" % (b0,b1,nm))
    if addr:
        for b0,b1,nm in mods:
            if b0 <= addr < b1:
                print("\n>>> ИСКЛЮЧЕНИЕ В: %s +0x%X" % (nm, addr-b0)); break
        else:
            print("\n>>> адрес вне списка модулей (unkernel/загружен позже)")
if 3 in st:
    r = st[3][1]; cnt = D.u32(d, r)
    print("\nпотоков в дампе:", cnt)
    for i in range(cnt):
        o = r + 4 + i*48
        tid, susp, prio = D.u32(d,o), D.u32(d,o+4), D.u32(d,o+8)
        teb = D.u64(d, o+16)
        ssz, srva = D.u32(d,o+24), D.u32(d,o+28)
        csz, crva = D.u32(d,o+32), D.u32(d,o+36)
        print("  tid=%-6d приоритет=%-3d стек=0x%012X(%d б) контекст=0x%X(%d б)" % (tid,prio,teb,ssz,crva,csz))

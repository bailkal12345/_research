import sqlite3, struct, collections
c = sqlite3.connect(r'C:\Dev\_research\v361.sqlite')
p = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ShooterGameServer.exe'
data = open(p,'rb').read()
e_lfanew = struct.unpack_from('<I', data, 0x3C)[0]
nsec = struct.unpack_from('<H', data, e_lfanew+6)[0]
optsz = struct.unpack_from('<H', data, e_lfanew+20)[0]
sec0 = e_lfanew+24+optsz
secs=[]
for i in range(nsec):
    o = sec0+40*i
    vsz, va, rsz, ra = struct.unpack_from('<IIII', data, o+8)
    secs.append((va, vsz, ra, rsz))
# rdata section
rdata = [s for s in secs if s[0]==0x3000000 or True]
# find the section containing 0x4004F40
for va,vsz,ra,rsz in secs:
    if va <= 0x4004F40 < va+vsz: RD=(va,vsz,ra,rsz)
names = {}
for rva, nm in c.execute("select rva,name from fn where rva is not null"):
    if rva: names.setdefault(rva, []).append(nm)
def show(va):
    l = names.get(va-0x140000000)
    return l[0] if l else "?"
va,vsz,ra,rsz = RD
N = (rsz)//8
base = ra
cnt = collections.Counter()
good=[]
w = lambda off: struct.unpack_from('<Q', data, base+off)[0]
for i in range(N-340):
    if w(i*8+0x350) == 0x142474DA0 and w(i*8+0x108) == 0x1424684E0 and w(i*8+0x058) == 0x14246F600:
        v319 = w(i*8+0x9f8)
        cnt[v319]+=1
        good.append((va+i*8, v319))
print("AActor-derived vtables found:", len(good))
for v,n in cnt.most_common(20):
    print("  idx319 -> %016X  %-70s x%d" % (v, show(v), n))

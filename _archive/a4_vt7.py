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
def rva2off(rva):
    for va,vsz,ra,rsz in secs:
        if va<=rva<va+max(vsz,rsz): return ra+(rva-va)
    return None
names = {}
for rva, nm in c.execute("select rva,name from fn where rva is not null"):
    if rva: names.setdefault(rva, []).append(nm)
def show(va):
    l = names.get(va-0x140000000)
    return (l[0] if l else "?")

# AShooterGameMode vtable
GM = 0x400F278
for off in (0x108, 0x350, 0x858, 0x9f8, 0xdb8, 0x0, 0x58):
    v = struct.unpack_from('<Q', data, rva2off(GM+off))[0]
    print("AShooterGameMode::vftable +0x%03X idx %3d = %016X  %s" % (off, off//8, v, show(v)))
print()
# find all vtables with AllowSaving at idx106
pat = struct.pack('<Q', 0x142474DA0)
cnt = collections.Counter()
st=0; bases=[]
while True:
    i = data.find(pat, st)
    if i<0: break
    st=i+1
    rva=None
    for va,vsz,ra,rsz in secs:
        if ra<=i<ra+rsz: rva = va+(i-ra)
    if rva is None: continue
    base = rva - 0x350
    v9f8 = struct.unpack_from('<Q', data, rva2off(base+0x9f8))[0]
    cnt[v9f8]+=1
    bases.append((base, v9f8))
print("vtables with AActor::AllowSaving at idx106:", len(bases))
for v,n in cnt.most_common(15):
    print("  idx319 -> %016X  %-60s  x%d" % (v, show(v), n))

import sqlite3, struct
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
    name = data[o:o+8].rstrip(b'\0').decode()
    vsz, va, rsz, ra = struct.unpack_from('<IIII', data, o+8)
    secs.append((name, va, vsz, ra, rsz))
def rva2off(rva):
    for n,va,vsz,ra,rsz in secs:
        if va<=rva<va+max(vsz,rsz): return ra+(rva-va)
    return None
def off2rva(off):
    for n,va,vsz,ra,rsz in secs:
        if ra<=off<ra+rsz: return va+(off-ra)
    return None

# rdb index: build dict rva->name from fn table
names = {}
for rva, nm in c.execute("select rva,name from fn"):
    if rva: names.setdefault(rva, nm)

def nm(va):
    rva = va-0x140000000
    return names.get(rva, '?')

target = struct.pack('<Q', 0x141FA83C0)  # &UObject::Serialize
hits = []
start = 0
while True:
    i = data.find(target, start)
    if i < 0: break
    hits.append(i); start = i+1
print("occurrences of &UObject::Serialize:", len(hits))
for i in hits[:20]:
    rva = off2rva(i)
    base_rva = rva - 19*8
    print("  @off %08X rva %08X -> candidate vtable base rva %08X (VA %016X)"%(i, rva, base_rva, 0x140000000+base_rva))

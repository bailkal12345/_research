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
    if rva: names.setdefault(rva, nm)
def nm(va):
    return names.get(va-0x140000000, '?')
def slot(base_rva, idx):
    off = rva2off(base_rva+idx*8)
    if off is None: return None
    return struct.unpack_from('<Q', data, off)[0]

target = struct.pack('<Q', 0x141FA83C0)
hits=[]; st=0
while True:
    i=data.find(target,st)
    if i<0: break
    hits.append(i); st=i+1
cnt = collections.Counter()
info=[]
for i in hits:
    rva_i = None
    for va,vsz,ra,rsz in secs:
        if ra<=i<ra+rsz: rva_i = va+(i-ra)
    base = rva_i - 19*8
    s350 = slot(base,0x350//8); s858=slot(base,0x858//8); s9f8=slot(base,0x9f8//8); s098=slot(base,0x98//8)
    info.append((base,s098,s350,s858,s9f8))
    cnt[(s098,s350,s858,s9f8)]+=1
print("total", len(info))
for k,v in cnt.most_common(8):
    print("count=%d  0x98=%s  0x350=%s  0x858=%s  0x9f8=%s"%(v, nm(k[0]) if k[0] else None, nm(k[1]) if k[1] else None, nm(k[2]) if k[2] else None, nm(k[3]) if k[3] else None))

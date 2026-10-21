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
    if not l: return "?"
    for x in l:
        if x.startswith('AActor::'): return x
    return l[0]
VT=0x411F268
tg={0x142479E90:'RerunConstructionScripts',0x142474DA0:'AllowSaving',0x14246F600:'PreSave',
    0x142474E70:'GetIsMapActor',0x1424684E0:'GetWorld',0x141FA83C0:'UObject::Serialize',
    0x141FAF8F0:'UPackage::Serialize',0x1424742E0:'?'}
for i in range(0,460):
    v = struct.unpack_from('<Q', data, rva2off(VT+i*8))[0]
    if v in tg:
        print("AActor::vftable idx %3d (+0x%03X) = %s" % (i, i*8, tg[v]))
print()
print("slots 310..330:")
for i in range(310,332):
    v = struct.unpack_from('<Q', data, rva2off(VT+i*8))[0]
    print("  idx %3d +0x%03X = %016X %s" % (i, i*8, v, show(v)))

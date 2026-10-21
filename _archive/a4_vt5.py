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
VT = 0x411F268
def show(va):
    l = names.get(va-0x140000000)
    if not l: return "?"
    # prefer a name containing AActor/UObject
    for x in l:
        if x.startswith('AActor::') or x.startswith('UObject::'): return x
    return l[0]
print("pre-slots:")
for off in range(-0x10, 0, 8):
    v = struct.unpack_from('<Q', data, rva2off(VT+off))[0]
    print("  %+03d = %016X %s" % (off, v, show(v)))
targets = {0x141FA83C0:'UObject::Serialize', 0x142474DA0:'AActor::AllowSaving', 0x14246F600:'AActor::PreSave',
           0x142474E70:'AActor::GetIsMapActor', 0x1424684E0:'AActor::GetWorld'}
found = {}
for i in range(0, 700):
    o = rva2off(VT+i*8)
    if o is None: break
    v = struct.unpack_from('<Q', data, o)[0]
    if v in targets:
        found[targets[v]] = i*8
        print("FOUND %-28s at +0x%X (idx %d)" % (targets[v], i*8, i))
print(found)

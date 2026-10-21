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
    if rva: names.setdefault(rva, nm)
def nm(va):
    if va is None: return '?'
    return "%016X %s" % (va, names.get(va-0x140000000, '?'))
VT = 0x411F268
for off in [0x0,0x28,0x30,0x50,0x58,0x70,0x88,0x90,0x98,0x100,0x108,0x300,0x308,0x310,0x318,0x320,0x338,0x340,0x348,0x350,0x358,0x360,0x368,0x370,0x378,0x380,0x388,0x390,0x398,0x3a0,0x850,0x858,0x860,0x9f0,0x9f8,0xa00,0xa08,0xb00,0xb08]:
    o = rva2off(VT+off)
    if o is None: print("0x%03X -> ?"%off); continue
    v = struct.unpack_from('<Q', data, o)[0]
    print("AActor vftable +0x%03X (idx %3d) = %s" % (off, off//8, nm(v)))

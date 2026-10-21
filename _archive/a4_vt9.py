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
    return l[0] if l else "?"
for label, VT in [("AActor",0x411F268), ("AShooterCharacter",0x400B1F0)]:
    print("===",label)
    for i in (5,11,19,106,218,267,319,318,320,311,312,313,314,315,316,317,322):
        v = struct.unpack_from('<Q', data, rva2off(VT+i*8))[0]
        print("  idx %3d +0x%03X = %016X %s" % (i, i*8, v, show(v)))

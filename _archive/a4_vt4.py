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
VT = 0x411F268
for off in range(0x9b0, 0xa20, 8):
    o = rva2off(VT+off)
    v = struct.unpack_from('<Q', data, o)[0]
    print("+0x%03X idx %3d = %016X  %s" % (off, off//8, v, names.get(v-0x140000000,'?')))
print()
for off in range(0x0, 0x100, 8):
    o = rva2off(VT+off)
    v = struct.unpack_from('<Q', data, o)[0]
    print("+0x%03X idx %3d = %016X  %s" % (off, off//8, v, names.get(v-0x140000000,'?')))

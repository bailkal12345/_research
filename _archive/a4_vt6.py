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
def show(va, prefer=None):
    l = names.get(va-0x140000000)
    if not l: return "?"
    if prefer:
        for x in l:
            if prefer in x: return x
    return l[0]
for cls in ['APrimalDinoCharacter','APrimalDino','AShooterCharacter','AShooterGameMode','APrimalItem','UPrimalInventoryComponent']:
    r = c.execute("select rva,size from fn where name=? and size>50",(cls+'::'+cls,)).fetchall()
    if not r:
        r = c.execute("select rva,size from fn where name like ? and name not like '%dtor%' order by size desc limit 3",('%'+cls+'::'+cls,)).fetchall()
    print(cls, [("%08X"%x[0],x[1]) for x in r])

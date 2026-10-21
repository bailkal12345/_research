import sqlite3, re, struct
c = sqlite3.connect(r'C:\Dev\_research\v361.sqlite')
rows = c.execute("select name,rva,size,tag from sym where name like '??_7AActor%' or name like '??_7APrimalDino%' or name like '??_7UPrimalInventoryComponent%'").fetchall()
for r in rows[:20]: print("%08X %d t%d %s"%(r[1],r[2],r[3],r[0]))

# Build rva->name map for a few classes
def symat(rva):
    r = c.execute("select name,size from fn where rva<=? order by rva desc limit 1",(rva,)).fetchone()
    return r

p = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ShooterGameServer.exe'
data = open(p,'rb').read()
import json
# PE parse
import struct
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
print([s[0] for s in secs])

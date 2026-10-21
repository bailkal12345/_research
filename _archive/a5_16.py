import struct, sqlite3, re
EXE=r"C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ShooterGameServer.exe"
d=open(EXE,"rb").read()
e_lfanew=struct.unpack_from("<I",d,0x3C)[0]
nsec=struct.unpack_from("<H",d,e_lfanew+6)[0]
optsz=struct.unpack_from("<H",d,e_lfanew+20)[0]
sec=e_lfanew+24+optsz
secs=[]
for i in range(nsec):
    o=sec+40*i
    name=d[o:o+8].rstrip(b"\0").decode()
    vsz,va,rsz,ra=struct.unpack_from("<IIII",d,o+8)
    secs.append((name,va,vsz,ra,rsz))
def r2o(rva):
    for n,va,vsz,ra,rsz in secs:
        if va<=rva<va+max(vsz,rsz): return ra+(rva-va)
    return None
c=sqlite3.connect(r"C:\Dev\_research\v361.sqlite"); cur=c.cursor()
cur.execute("SELECT name,rva,size FROM fn WHERE name LIKE ? AND name LIKE ? ORDER BY rva",("%UObjectexec%","%BytecodeTemp%"))
rows=sorted(set(cur.fetchall()))
GN=0x491C6B0
res={}
for n,rva,sz in rows:
    if not (0xA0000<=rva<0x40000): continue
    o=r2o(rva)
    if o is None: continue
    b=d[o:o+160]
    nm=re.search(r"UObjectexec(\w+)BytecodeTemp",n).group(1)
    best=None
    for i in range(len(b)-10):
        if b[i:i+3]==b"\x48\xc7\x05":
            disp=struct.unpack_from("<i",b,i+3)[0]
            imm=struct.unpack_from("<I",b,i+7)[0]
            rip=rva+i+7
            target=rip+disp
            if (target-GN)%8==0 and 0<=(target-GN)//8<256:
                best=((target-GN)//8, imm, i)
    if best:
        res[nm]=best[0]
        print("op 0x%02X  %-28s -> RVA 0x%08X" % (best[0], nm, best[1]))
    else:
        print("op  ???  %-28s  NOT FOUND" % nm)
print("RESOLVED", len(res), "of", len([1 for n,r,s in rows if 0xA0000<=r<0x40000]))
missing=[i for i in range(256) if i not in res.values()]
print("unused opcode slots:", missing)

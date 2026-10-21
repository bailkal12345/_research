import struct, sqlite3, re
EXE=r"C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ShooterGameServer.exe"
d=open(EXE,"rb").read()
e=struct.unpack_from("<I",d,0x3C)[0]
nsec=struct.unpack_from("<H",d,e+6)[0]; optsz=struct.unpack_from("<H",d,e+20)[0]
sec=e+24+optsz; secs=[]
for i in range(nsec):
    o=sec+40*i
    vsz,va,rsz,ra=struct.unpack_from("<IIII",d,o+8)
    secs.append((va,vsz,ra,rsz))
def r2o(rva):
    for va,vsz,ra,rsz in secs:
        if va<=rva<va+max(vsz,rsz): return ra+(rva-va)
c=sqlite3.connect(r"C:\Dev\_research\v361.sqlite"); cur=c.cursor()
cur.execute("SELECT name,rva,size FROM fn WHERE name LIKE ? AND name LIKE ?",("%UObjectexec%","%BytecodeTemp%"))
rows=sorted(set(cur.fetchall()))
GN=0x491C6B0; res={}
for n,rva,sz in rows:
    if rva>=0x100000: continue
    o=r2o(rva); b=d[o:o+160]
    nm=re.search(r"UObjectexec(\w+)BytecodeTemp",n).group(1)
    best=None
    for i in range(len(b)-11):
        if b[i:i+3]==b"\x48\xc7\x05":
            disp=struct.unpack_from("<i",b,i+3)[0]; imm=struct.unpack_from("<I",b,i+7)[0]
            t=rva+i+7+disp
            if (t-GN)%8==0 and 0<=(t-GN)//8<256: best=((t-GN)//8,imm)
    if best:
        res[nm]=best[0]
        print("op 0x%02X  %-26s -> UObject::exec%s @ RVA 0x%08X"%(best[0],nm,nm,best[1]))
    else: print("op  ???  %-26s NOT FOUND"%nm)
print("RESOLVED",len(res))
print("unassigned opcode slots:",[i for i in range(256) if i not in res.values()])

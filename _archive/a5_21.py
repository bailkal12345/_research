import struct, sqlite3
EXE=r"C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ShooterGameServer.exe"
d=open(EXE,"rb").read()
e=struct.unpack_from("<I",d,0x3C)[0]
nsec=struct.unpack_from("<H",d,e+6)[0]; optsz=struct.unpack_from("<H",d,e+20)[0]
sec=e+24+optsz; secs=[]
for i in range(nsec):
    o=sec+40*i; vsz,va,rsz,ra=struct.unpack_from("<IIII",d,o+8); secs.append((va,vsz,ra,rsz))
def r2o(rva):
    for va,vsz,ra,rsz in secs:
        if va<=rva<va+max(vsz,rsz): return ra+(rva-va)
b=d[r2o(0x1F0FE0):r2o(0x1F0FE0)+45]
print("UObjectBaseUtility::GetName RVA 0x1F0FE0 (45 B):")
print(" ".join("%02X"%x for x in b))
c=sqlite3.connect(r"C:\Dev\_research\v361.sqlite"); cur=c.cursor()
for nm in ["UFunction::Bind","UFunction::SetNativeFunc","UObject::ProcessEvent","FName::ToString","UFunction::Invoke","UObject::ProcessInternal","UObject::ProcessContextOpcode","UObject::CallFunction","UFunction::GetReturnProperty","UObject::ExecuteUbergraph"]:
    cur.execute("SELECT DISTINCT name,rva,size FROM fn WHERE name=?",(nm,))
    for n,r,s in cur.fetchall(): print("0x%08X %6d  %s"%(r,s,n))

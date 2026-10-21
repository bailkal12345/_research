import struct
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
for rva,sz in [(0xA00D0,127),(0xA1030,130),(0xA0A10,130)]:
    o=r2o(rva); b=d[o:o+sz]
    print("=== RVA 0x%X size %d ==="%(rva,sz))
    for i in range(0,len(b),16):
        print("  +%03X %08X  %s"%(i, rva+i, " ".join("%02X"%x for x in b[i:i+16])))

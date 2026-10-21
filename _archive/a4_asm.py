import struct
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
BASE=0x2755CC0; SIZE=8788
o=rva2off(BASE); blob=data[o:o+SIZE]
pats = {b'\x50\x03\x00\x00':'disp 0x350', b'\xf8\x09\x00\x00':'disp 0x9f8', b'\x58\x08\x00\x00':'disp 0x858',
        b'\x98\x00\x00\x00':'disp 0x98', b'\xb8\x0d\x00\x00':'disp 0xdb8'}
for pat,label in pats.items():
    st=0
    hits=[]
    while True:
        i=blob.find(pat,st)
        if i<0: break
        hits.append(i); st=i+1
    print("--- %s : %d hits"%(label,len(hits)))
    for h in hits[:12]:
        lo=max(0,h-8)
        print("   rva %08X : %s"%(BASE+h, blob[lo:h+8].hex(' ')))

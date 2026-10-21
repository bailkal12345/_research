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
BASE=0xCDC220; SIZE=4291
o=rva2off(BASE); blob=data[o:o+SIZE]
targets={0x3D8250:'FGraphEvent::IsComplete',0x1F5B9D0:'FWindowsPlatformProcess::Sleep',
         0xCDC220:'self',0xD1FF40:'GetSaveDirectoryName'}
res={}
for i in range(len(blob)-5):
    if blob[i]==0xE8:
        d=struct.unpack_from('<i',blob,i+1)[0]; t=BASE+i+5+d
        if t in targets and t!=0xCDC220:
            res.setdefault(targets[t],[]).append(BASE+i)
for k,vv in res.items(): print("%-32s %s"%(k,["%08X"%x for x in vv]))

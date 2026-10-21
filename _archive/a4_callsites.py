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
targets = {0x276DC40:'TGraphTask<FWriteFileTask>::ConstructAndDispatchWhenReady',
           0x2755AF0:'ShouldSerializeTransform',
           0x1FD8340:'WorldSerializedObject::SerializeHeaders',
           0x1FD8FA0:'WorldSerializedObject::SerializeObjectData',
           0x1FD8020:'WorldSerializedObject::WorldSerializedObject',
           0x1DE4D0:'TMemoryWriter<32>::Serialize',
           0x1FD9150:'WorldSerializedObject::Begin',
           0x1FD9270:'WorldSerializedObject::End'}
res={}
for i in range(len(blob)-5):
    if blob[i]==0xE8:
        d = struct.unpack_from('<i', blob, i+1)[0]
        tgt = BASE+i+5+d
        if tgt in targets:
            res.setdefault(targets[tgt], []).append(BASE+i)
for k,vv in res.items():
    print("%-52s %s" % (k, ["%08X"%x for x in vv]))
for k in targets:
    if k not in res: print("%-52s <no direct call>"%k)

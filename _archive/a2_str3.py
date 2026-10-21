import re, struct
p = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ShooterGameServer.exe'
data = open(p,'rb').read()

def cstr(i, wide=False):
    step = 2 if wide else 1
    s=i
    while s>0 and 32<=data[s-step]<127: s-=step
    e=i
    while e<len(data) and 32<=data[e]<127: e+=step
    return data[s:e].decode('utf-16-le' if wide else 'latin1')

print("### region around ServerOctreeGroup enum names (utf16)")
base=63231434
for off in range(63231300, 63232300):
    if data[off-1:off+1]==b'\x00\x00' and off%2==0:
        pass
# simpler: dump utf16 strings near
seen=set()
i=63231300
while i < 63232500:
    # look for ascii-range utf16 char
    if 32 <= data[i] < 127 and data[i+1]==0:
        st=cstr(i, True)
        if 2<len(st)<80 and st not in seen:
            seen.add(st); print('  0x%08X %r'%(i, st))
            i+=len(st)*2
            continue
    i+=1

print("### region around bForceActorLocationDistanceCheck")
seen=set(); i=63280400
while i < 63282200:
    if 32 <= data[i] < 127 and data[i+1]==0:
        st=cstr(i, True)
        if 2<len(st)<90 and st not in seen:
            seen.add(st); print('  0x%08X %r'%(i, st))
            i+=len(st)*2; continue
    i+=1
import re
p = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ShooterGameServer.exe'
data = open(p,'rb').read()
def scan(pat, flags=re.I):
    idxs=[m.start() for m in re.finditer(pat, data, flags)]
    print('==', pat, len(idxs))
    seen=set()
    for i in idxs[:25]:
        s=i
        while s>0 and 32<=data[s-1]<127: s-=1
        e=i
        while e<len(data) and 32<=data[e]<127: e+=1
        st=data[s:e].decode('latin1')
        if len(st)>140: st=st[:140]+'...'
        if st in seen: continue
        seen.add(st)
        print('   0x%08X %r'%(s,st))
scan(b'Octree')
scan(b'ForceActorLocation')
# UTF16
for t in ['ServerOctreeGroup','bForceActorLocationDistanceCheck']:
    u = t.encode('utf-16-le')
    idxs=[m.start() for m in re.finditer(re.escape(u), data)]
    print('== utf16', t, len(idxs), idxs[:5])
import re, sys
p = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ShooterGameServer.exe'
data = open(p,'rb').read()
targets = [b'ServerOctreeGroup', b'bForceActorLocationDistanceCheck', b'ActorLocationDistanceCheck']
for t in targets:
    idxs = [m.start() for m in re.finditer(re.escape(t), data)]
    print('==', t, 'count', len(idxs))
    for i in idxs[:6]:
        # print the surrounding ascii-null-terminated string
        s = i
        while s > 0 and 32 <= data[s-1] < 127: s -= 1
        e = i
        while e < len(data) and 32 <= data[e] < 127: e += 1
        print('   fo=0x%08X  str=%r' % (s, data[s:e].decode('latin1')))
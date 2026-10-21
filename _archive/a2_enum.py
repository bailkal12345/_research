import re
p = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ShooterGameServer.exe'
data = open(p,'rb').read()
names=[]
for m in re.finditer(b'E\x00S\x00e\x00r\x00v\x00e\x00r\x00O\x00c\x00t\x00r\x00e\x00e\x00G\x00r\x00o\x00u\x00p\x00:\x00:\x00', data):
    i=m.start(); e=i
    while e<len(data) and 32<=data[e]<127 and data[e+1]==0: e+=2
    s=data[i:e].decode('utf-16-le')
    if s not in names: names.append(s)
print("EServerOctreeGroup enumerators found:", len(names))
for s in sorted(names): print("  ", s)

print()
print("### search for other enum-ish param names near Z_Construct_UEnum_UVictoryCore_EServerOctreeGroup")
# look for the FEnumProperty params names / the enum's enumerator list may be built at runtime;
# instead dump all 'Xxx::YYY' style enumerators that occur in the same rdata neighbourhood 0x3C4D000-0x3C4E000
seen=[]
i=0x3C4C000
while i < 0x3C4E000:
    if 32<=data[i]<127 and data[i+1]==0:
        e=i
        while e<len(data) and 32<=data[e]<127 and data[e+1]==0: e+=2
        s=data[i:e].decode('utf-16-le')
        if 3<len(s)<70 and '::' in s and s not in seen:
            seen.append(s)
        i=e; continue
    i+=1
for s in seen: print("  0x%08X %s"%(0,s))
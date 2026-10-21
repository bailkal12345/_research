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
def wstr(rva, n=120):
    o = rva2off(rva)
    b = data[o:o+n*2]
    s = b.decode('utf-16-le', errors='replace').split('\x00')[0]
    return s
BASE=0xCFDA20; SIZE=1718
o=rva2off(BASE); blob=data[o:o+SIZE]
seen=set()
for i in range(len(blob)-7):
    if blob[i]==0x48 and blob[i+1]==0x8D:
        disp = struct.unpack_from('<i', blob, i+3)[0]
        mod = blob[i+2]
        tgt = 0x140000000 + (BASE+i+7) + disp
        rva = tgt-0x140000000
        if 0x3000000 < rva < 0x6000000 and rva not in seen:
            seen.add(rva)
            try:
                s = wstr(rva)
            except Exception:
                continue
            if len(s) > 3 and all(32 <= ord(ch) < 0x3000 for ch in s):
                print("%08X  %r" % (rva, s.encode('ascii','replace').decode()))

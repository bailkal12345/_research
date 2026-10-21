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
def wstr(rva, n=90):
    o = rva2off(rva)
    b = data[o:o+n*2]
    try: return b.decode('utf-16-le').split('\x00')[0]
    except: return repr(b[:40])
for a in (0x3DE65D8, 0x3DE6308, 0x3DE4058, 0x3C85CA0, 0x3C85C58):
    print("%08X -> %r" % (a, wstr(a)))

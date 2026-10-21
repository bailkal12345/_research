import sqlite3, struct
c = sqlite3.connect(r'C:\Dev\_research\v361.sqlite')
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
names = {}
for rva, nm in c.execute("select rva,name from fn where rva is not null"):
    if rva: names.setdefault(rva, []).append(nm)
def show(va):
    l = names.get(va-0x140000000)
    return l[0] if l else "?"

def find_vtables(rva, size):
    o = rva2off(rva); blob = data[o:o+size]
    out=[]
    for i in range(len(blob)-7):
        if blob[i] in (0x48,) and blob[i+1] in (0x8D,0x8B):
            mod = blob[i+1]
            # 48 8D 0D=rip+rcx, 05=rax, 15=rdx, 1D=rbx, 25=rsp, 2D=rbp; 8B 0D=mov
            reg = {0x05:0,0x0D:1,0x15:2,0x1D:3,0x25:4,0x2D:5}.get(blob[i+2])
            if reg is None: continue
            disp = struct.unpack_from('<i', blob, i+3)[0]
            tgt = 0x140000000 + (rva+i+7) + disp
            if 0x144000000 <= tgt < 0x145000000:
                out.append((rva+i, tgt-0x140000000, reg))
    return out

for cname, rva, size in [("APrimalDinoCharacter",0x5CE5A0,15034), ("APrimalItem",None,0)]:
    if rva is None: continue
    print("===", cname)
    for at, vt, reg in find_vtables(rva,size)[:20]:
        # only those followed by a mov [reg],reg store
        o = rva2off(at)
        nxt = data[o+7:o+13]
        print("   at rva %08X -> vtable %08X reg=%d  next=%s" % (at, vt, reg, nxt.hex()))

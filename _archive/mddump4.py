import struct, sys, glob, os, bisect
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

def readutf(d, rva):
    try:
        ln, = struct.unpack_from('<I', d, rva)
        return d[rva+4:rva+4+ln].decode('utf-16-le')
    except Exception:
        return '?'

def parse(path):
    print('== ' + os.path.basename(path))
    d = open(path,'rb').read()
    nsig, = struct.unpack_from('<I', d, 8)
    dirrva, = struct.unpack_from('<I', d, 12)
    dirs = {}
    for i in range(nsig):
        t, sz, off = struct.unpack_from('<III', d, dirrva + 12*i)
        if t: dirs[t] = (sz, off)
    mods = []
    sz, off = dirs[4]
    n, = struct.unpack_from('<I', d, off)
    for i in range(n):
        base, size, cks, ts, nam = struct.unpack_from('<QIIII', d, off+4+108*i)
        mods.append((base, size, readutf(d, nam)))
    # exception
    sz, off = dirs[6]
    etid, = struct.unpack_from('<I', d, off)
    ecode, eflags, erec, eaddr = struct.unpack_from('<IIQQ', d, off+8)
    print('  exc tid=%d code=0x%x addr=0x%x' % (etid, ecode, eaddr))
    # memory list (type5): NumberOfRanges(4) NumberOfDescriptors(4)? Actually MemoryListStream: NumRanges(4)+NumDescriptors(4), then descriptors (StartOfMemoryRange(8)+DataSize(4)+Rva(4)) each 16 bytes
    sz, off = dirs[5]
    n2, = struct.unpack_from('<I', d, off)
    mems = []
    for i in range(n2):
        start, msize, rva = struct.unpack_from('<QII', d, off+4+16*i)
        mems.append((start, msize, rva))
    mems.sort()
    starts = [m[0] for m in mems]
    def memread(addr, ln):
        i = bisect.bisect_right(starts, addr) - 1
        if i < 0: return None
        start, msize, rva = mems[i]
        if start + msize <= addr: return None
        o = rva + (addr - start)
        return d[o:o+ln]
    # thread list
    sz, off = dirs[3]
    n, = struct.unpack_from('<I', d, off)
    for i in range(n):
        tb = off + 4 + 48*i
        tid, susp, prioc, prio, teb, ststart, stsize, strva, tcsize, tcrva = struct.unpack_from('<IIIIQQIIII', d, tb)
        if tid != etid: continue
        rsp = struct.unpack_from('<Q', d, tcrva + 0x90)[0]
        rsp2 = struct.unpack_from('<Q', d, tcrva + 0x98)[0]
        rbp = struct.unpack_from('<Q', d, tcrva + 0xA0)[0]
        rip, = struct.unpack_from('<Q', d, tcrva + 0xF8)
        print('  cand RSP@0x90=%x @0x98=%x RBP@0xA0=%x RIP=%x' % (rsp, rsp2, rbp, rip))
        best = next((x for x in (rsp2, rsp) if x > 0x1000000), 0)
        if not best: return
        def modof(a):
            for (base, size, nm) in mods:
                if base <= a < base + size:
                    return '%s +0x%x' % (os.path.basename(nm), a - base)
            return None
        buf = memread(best, 0x600) or b''
        for j in range(0, len(buf) - 8, 8):
            v, = struct.unpack_from('<Q', buf, j)
            m = modof(v)
            if m and 'ShooterGame.exe' in m:
                print('   [rsp+0x%x] ret %s' % (j, m))
    return

if __name__ == '__main__':
    dd = r'C:\Games\ARK_SE_game_v361\ShooterGame\Saved\Logs'
    ps = sorted(glob.glob(os.path.join(dd,'Dump-*.dmp')), key=os.path.getmtime, reverse=True)
    for p in ps[:1]:
        parse(p)

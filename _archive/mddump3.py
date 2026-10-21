import struct, sys, glob, os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ST = {3:'ThreadList',4:'ModuleList',5:'MemoryList',6:'Exception',7:'SystemInfo',
      8:'MemoryListOld',9:'Memory64List',11:'HandleData',14:'MiscInfo',16:'MemoryInfoList',17:'ThreadInfoList',22:'CommentStreamW',23:'SystemMemInfo'}

def readutf(d, rva):
    try:
        ln, = struct.unpack_from('<I', d, rva)
        return d[rva+4:rva+4+ln].decode('utf-16-le')
    except Exception:
        return '<rva 0x%x?' % rva

def parse(path):
    print('== ' + os.path.basename(path))
    d = open(path,'rb').read()
    if d[:4] != b'MDMP':
        print('  not minidump'); return
    nsig, = struct.unpack_from('<I', d, 8)
    dirrva, = struct.unpack_from('<I', d, 12)
    dirs = {}
    for i in range(nsig):
        t, sz, off = struct.unpack_from('<III', d, dirrva + 12*i)
        name = ST.get(t, ('type%d' % t))
        dirs[t] = (sz, off)
        print('  %-16s off=%#x size=%d' % (name, off, sz))
    mods = []
    if 4 in dirs:
        sz, off = dirs[4]
        n, = struct.unpack_from('<I', d, off)
        print('  #modules=%d' % n)
        for i in range(n):
            base, size, cks, ts, nam = struct.unpack_from('<QIIII', d, off+4+108*i)
            mods.append((base, size, readutf(d, nam)))
        for base, size, nm in mods[:8]:
            print('   0x%016x %9d %s' % (base, size, nm))
    exc = {}
    if 6 in dirs:
        sz, off = dirs[6]
        tid, = struct.unpack_from('<I', d, off)
        code, flags, rec, addr = struct.unpack_from('<IIQQ', d, off+12)
        tsize, trva = struct.unpack_from('<II', d, off+44)
        exc = dict(tid=tid, code=code, addr=addr, trva=trva)
        print('  exception tid=%d code=0x%08x addr=0x%016x ctxsize=%#x rva=%#x' % (tid, code, addr, tsize, trva))
        hit = [m for m in mods if m[0] <= addr < m[0]+m[1]]
        if hit:
            print('  in module %s rva=0x%x' % (hit[0][2], addr - hit[0][0]))
        rsp = struct.unpack_from('<Q', d, trva+0x98)[0]
        rip = struct.unpack_from('<Q', d, trva+0xF8)[0]
        print('  RSP=0x%x RIP=0x%x (%s +0x%x)' % (rsp, rip, (hit[0][2] if hit else '?'), (rip - hit[0][0]) if hit else 0))
    return mods, exc

if __name__ == '__main__':
    dd = r'C:\Games\ARK_SE_game_v361\ShooterGame\Saved\Logs'
    ps = sorted(glob.glob(os.path.join(dd,'Dump-*.dmp')), key=os.path.getmtime, reverse=True)
    print('dumps: %d' % len(ps))
    for p in ps[:2]:
        parse(p)

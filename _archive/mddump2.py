import struct, sys, glob, os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ST = {0:'Unused',3:'ThreadList',4:'ModuleList',5:'MemoryList',6:'Exception',7:'SystemInfo',
      8:'MemoryListOld',9:'Memory64List',11:'HandleData',12:'FunctionTable',13:'UnloadedModules',
      14:'MiscInfo',16:'MemoryInfoList',17:'ThreadInfoList'}

def parse(path):
    print('== ' + os.path.basename(path))
    d = open(path,'rb').read()
    if d[:4] != b'MDMP':
        print('  not minidump'); return
    nsig = struct.unpack_from('<I', d, 8)[0]
    dirs = {}
    for i in range(nsig):
        t, sz, off = struct.unpack_from('<III', d, 16 + 12*i)
        dirs[t] = (sz, off)
    # modules
    mods = []
    if 4 in dirs:
        sz, off = dirs[4]
        n, = struct.unpack_from('<I', d, off)
        for i in range(n):
            base, size, cks, ts, namerva = struct.unpack_from('<QIIII', d, off+4+108*i)
            nm = readutf(d, namerva)
            mods.append((base, size, nm))
    print('  #modules=%d' % len(mods))
    for base, size, nm in mods[:12]:
        print('   0x%016x %8d %s' % (base, size, nm))
    # exception
    if 6 in dirs:
        sz, off = dirs[6]
        tid, = struct.unpack_from('<I', d, off)
        code, flags, rec, addr = struct.unpack_from('<IIQQ', d, off+12)
        print('  exception tid=%d code=0x%08x addr=0x%016x' % (tid, code, addr))
        hit = [m for m in mods if m[0] <= addr < m[0] + m[1]]
        for base, size, nm in hit[:1]:
            print('  in module %s rva=0x%x' % (nm, addr - base))
        # thread context: after ExceptionRecord(32) comes MINIDUMP_LOCATION_DESCRIPTOR (size,rva)
        tsize, trva = struct.unpack_from('<II', d, off+44)
        if tsize >= 0x400:
            pos = trva
            rsp = struct.unpack_from('<Q', d, pos+0x98)[0]
            rip = struct.unpack_from('<Q', d, pos+0xF8)[0]
            print('  ctx RSP=0x%x RIP=0x%x' % (rsp, rip))
            return mods, rsp, addr
    return mods, None, None

def readutf(d, rva):
    try:
        ln, = struct.unpack_from('<I', d, rva)
        return d[rva+4:rva+4+ln].decode('utf-16-le')
    except Exception:
        return '<rva 0x%x?' % rva

if __name__ == '__main__':
    dd = r'C:\Games\ARK_SE_game_v361\ShooterGame\Saved\Logs'
    ps = sorted(glob.glob(os.path.join(dd,'Dump-*.dmp')), key=os.path.getmtime, reverse=True)
    print('dumps:', len(ps))
    for p in ps[:2]:
        parse(p)

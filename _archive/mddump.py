import struct, sys, glob, os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

class Mini:
    def __init__(self, path):
        self.d = open(path, 'rb').read()
        d = self.d
        assert d[:4] == b'MDMP'
        self.nstreams, = struct.unpack_from('<I', d, 8)
        self.dirs = {}
        self.mods = []
        self.memblocks = []   # (startaddr, rva, size) -> file offset rva
        for i in range(self.nstreams):
            t, sz, off = struct.unpack_from('<III', d, 16 + 12*i)
            self.dirs[t] = (sz, off)
        if 4 in self.dirs:
            sz, off = self.dirs[4]
            n, = struct.unpack_from('<I', d, off)
            for i in range(n):
                base, size, cks, ts, namerva = struct.unpack_from('<QIIII', d, off+4+108*i)
                self.mods.append((base, size, namerva))
        mt = 9 if 9 in self.dirs else 8
        if mt in self.dirs:
            sz, off = self.dirs[mt]
            rangecount, , storage = 0,0,0
            # MemoryListStream: NumberOfMemoryRanges(4), NumberOfStreams? For Memory64ListStream different
            rangecount, = struct.unpack_from('<Q', d, off) if mt == 9 else (0,)
            if mt == 9:  # MemoryListStream: count(4) then MINIDUMP_MEMORY_DESCRIPTOR[start(8), size(4)]*n
                rangecount, = struct.unpack_from('<I', d, off)
                for i in range(rangecount):
                    start, msize = struct.unpack_from('<QI', d, off+4+12*i)
                    # MemoryListStream has no initial start rva; each descriptor has DataSize+Rva
                    pass
        if 8 in self.dirs:  # MemoryListStream
            sz, off = self.dirs[8]
            cnt, = struct.unpack_from('<I', d, off)
            rc, = struct.unpack_from('<I', d, off)  # MemoryRanges then MemoryDescriptors
            dcnt, = struct.unpack_from('<I', d, off)
            n1, n2 = struct.unpack_from('<II', d, off)  # MemoryRangeCount, MemoryDescriptorCount? Actually MemoryListStream is: NumRanges(4) NumDescriptors(4) then descriptors
            for i in range(n2):
                start, msize, rva = struct.unpack_from('<QII', d, off+8+16*i)
                self.memblocks.append((start, rva, msize))
        else:
            # memory64
            sz, off = self.dirs[9] if 9 in self.dirs else (0, 0)
            if 9 in self.dirs:
                sz, off = self.dirs[9]
                base, n1, n2 = struct.unpack_from('<QII', d, off)
                # descriptors after header + stride array of base RVAS? Memory64ListStream: StartOfMemoryRange(8), NumberOfDescriptors(8), BaseRva(8), then [StartOfMemoryRange(8)*n1], then [DataSize(8), Rva(8)]*n2
                start, n1, n2 = struct.unpack_from('<QQQ', d, off)
                pos = off + 24 + 8*n1
                for i in range(n2):
                    msize, mstart = struct.unpack_from('<QQ', d, pos + 16*i)
                    self.memblocks.append((mstart, start, msize))  # rva not needed yet
                    # base rva increment handled later
        # store BaseRva for memory64
        self.baseRva = 0
        if 9 in self.dirs and not 8 in self.dirs:
            sz, off = self.dirs[9]
            _, _, self.baseRva = struct.unpack_from('<QQQ', d, off)
        self.mem64 = []
        if 9 in self.dirs and not 8 in self.dirs:
            sz, off = self.dirs[9]
            start, n1, n2 = struct.unpack_from('<QQQ', d, off)
            pos = off + 24 + 8*n1
            self.mem64 = [struct.unpack_from('<QQ', d, pos + 16*i) for i in range(n2)]
        self.exc = None

    def modules(self):
        out = []
        d = self.d
        for (base, size, namerva) in self.mods:
            nm = self.read_utf16_rva(namerva)
            out.append((base, size, nm))
        return out

    def read_utf16_rva(self, rva):
        off = self.rva2off(rva)
        if off is None:
            # try memory64 mapping
            return "<rva?>"
        ln, = struct.unpack_from('<I', self.d, off)
        try:
            return self.d[off+4:off+4+ln].decode('utf-16-le')
        except Exception:
            return "<bad>"

    def rva2off(self, rva):
        # memory64: compute cumulative
        if self.mem64offs is not None:
            # binary search
            import bisect
            idx = bisect.bisect_right(self.rvas, rva) - 1
            if 0 <= idx < len(self.rvas):
                r0, sz, _ = self.memdescs[idx]
                if r0 <= rva < r0 + sz:
                    return self.rvaofflist[idx] + (rva - r0)
        # fallback memory list rva->offset from memblocks (rva stored)
        for (start, rva, size) in self.memblocks:
            if rva <= rva < rva + size:
                return rva
        return None

    def prepare64(self):
        self.rvas = []
        self.memdescs = []
        self.rvaofflist = []
        base = self.baseRva
        for (sz, start) in self.mem64:
            self.memdescs.append((base, sz, start))
            self.rvas.append(base)
            self.rvaofflist.append(base)
            base += sz

    def exception(self):
        if self.exc:
            return self.exc
        if 6 not in self.dirs:
            return None
        d = self.d
        off, sz = self.dirs[6]
        tid, = struct.unpack_from('<I', d, off)
        code, flags, rec, addr = struct.unpack_from('<IIQQ', d, off+12)
        # interface thread context size/rva next? MINIDUMP_EXCEPTION_STREAM: ThreadId(4)+__alignment(4)+ExceptionRecord(32)+ThreadContext(8)
        tsize, trva = struct.unpack_from('<II', d, off+44)
        # then MINIDUMP_THREAD follows
        self.exc = dict(tid=tid, code=code, addr=addr, tsize=tsize, trva=trva)
        return self.exc


def parse(path):
    print('== ' + os.path.basename(path))
    m = Mini(path)
    m.prepare64()
    exc = m.exception()
    if exc:
        ctx = m.read_utf16_rva  # not used
        print('  exception tid=%d code=0x%08x addr=0x%016x tctx rva=%d size=%d' % (exc['tid'], exc['code'], exc['addr'], exc['trva'], exc['tsize']))
        mods = m.modules()
        print('  #modules=%d' % len(mods))
        hit = [x for x in mods if x[0] <= exc['addr'] < x[0]+x[1]]
        print('  --- mod: ' + (hit[0][2] if hit else '???') + (' rva=0x%x' % (exc['addr'] - hit[0][0]) if hit else ''))
        # print first/exception thread stack pointers from context (RSP at ctx)
        rsp = readctx(m, exc, 'RSP')
        rip = readctx(m, exc, 'RIP')
        print('  context RSP=0x%x RIP=0x%x' % (rsp or 0, rip or 0))
    return m

def readctx(m, exc, reg):
    # find thread context via trva: MINIDUMP_LOCATION_DESCRIPTOR(trva,size) -> CONTEXT stru
    off = m.rva2off(exc['trva'])
    if off is None:
        return None
    d = m.d
    idx = {'RIP': 0xF8, 'RSP': 0x98}
    pos = off + idx.get(reg, 0)
    if pos+8 > len(d):
        return None
    return struct.unpack_from('<Q', d, pos)[0]

if __name__ == '__main__':
    dd = r'C:\Games\ARK_SE_game_v361\ShooterGame\Saved\Logs'
    ps = sorted(glob.glob(os.path.join(dd, 'Dump-*.dmp')), key=os.path.getmtime, reverse=True)
    for p in ps[:2]:
        parse(p)

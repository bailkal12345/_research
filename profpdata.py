# -*- coding: utf-8 -*-
# Parsing the .pdata (RUNTIME_FUNCTION) of the exe + binding profile leaves/ret to functions.
import struct, bisect, collections, sys
import profanalyze as pa

EXE = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ShooterGameServer.exe'
TICKPROF = pa.TICKPROF

def get_pdata(path):
    with open(path, 'rb') as f:
        hdr = f.read(1 << 12)
    pe_off = struct.unpack_from('<I', hdr, 0x3C)[0]
    coff = pe_off + 4
    opt_size = struct.unpack_from('<H', hdr, coff + 16)[0]
    opt = coff + 20
    exp_rva = struct.unpack_from('<I', hdr, opt + 112 + 3 * 8)[0]  # DataDirectory[3] = Exception
    exp_size = struct.unpack_from('<I', hdr, opt + 112 + 3 * 8 + 4)[0]
    nsec = struct.unpack_from('<H', hdr, coff + 2)[0]
    sec_off = opt + opt_size
    sections = []
    for i in range(nsec):
        s = sec_off + i * 40
        vsize = struct.unpack_from('<I', hdr, s + 8)[0]
        vaddr = struct.unpack_from('<I', hdr, s + 12)[0]
        rawptr = struct.unpack_from('<I', hdr, s + 20)[0]
        sections.append((vaddr, vsize, rawptr))
    def rva2off(rva):
        for vaddr, vsz, rawptr in sections:
            if vaddr <= rva < vaddr + vsz:
                return rawptr + (rva - vaddr)
        return None
    pd_off = rva2off(exp_rva)
    with open(path, 'rb') as f:
        f.seek(pd_off)
        data = f.read(exp_size)
    n = len(data) // 12
    funcs = []
    for i in range(n):
        s, e, _u = struct.unpack_from('<III', data, i * 12)
        funcs.append((s, e))
    funcs.sort()
    return funcs

def load_mods_and_wordlists(name):
    mods, bases = pa.load_modules(TICKPROF + '\\prof_%s.modules.txt' % name)
    bindata = open(TICKPROF + '\\prof_%s.bin' % name, 'rb').read()
    base_exe = struct.unpack_from('<Q', bindata, 0)[0]
    cnt = struct.unpack_from('<Q', bindata, 8)[0]
    rips = struct.unpack_from('<%dQ' % cnt, bindata, 16)
    ret_data = open(TICKPROF + '\\prof_%s.ret' % name, 'rb').read()
    rets = struct.unpack_from('<%dQ' % cnt, ret_data)
    return mods, bases, rips, rets, base_exe, cnt

def main():
    funcs = get_pdata(EXE)
    starts = [f[0] for f in funcs]
    print('functions in .pdata: %d; first start=0x%X, last end=0x%X' % (
        len(funcs), funcs[0][0], funcs[-1][1]))
    # check: do the functions cover the whole .text
    text_end = 0
    for va, ve, nm in pa.parse_sections(EXE) or []:
        if nm == '.text':
            text_end = ve
            text_start = va
    covered = 0
    for s, e in funcs:
        covered += e - s
    print('.text = [0x%X..0x%X] (0x%X bytes), covered by functions 0x%X bytes' % (
        text_start, text_end, text_end - text_start, covered))

    names = sys.argv[1:] or ['512222984', '383773968', '343238843', '209283656', '301269000']
    out = []
    for name in names:
        try:
            mods, bases, rips, rets, base_exe, cnt = load_mods_and_wordlists(name)
        except Exception as ex:
            print('prof %s: error %s' % (name, ex))
            continue
        lf = collections.Counter()
        rf = collections.Counter()
        for rip, ret in zip(rips, rets):
            if base_exe <= rip < base_exe + text_end:
                off = rip - base_exe
                i = bisect.bisect_right(starts, off) - 1
                if 0 <= i and off < funcs[i][1]:
                    lf[funcs[i][0]] += 1
            if base_exe <= ret < base_exe + text_end:
                off = ret - base_exe
                i = bisect.bisect_right(starts, off) - 1
                if 0 <= i and off < funcs[i][1]:
                    rf[funcs[i][0]] += 1
        out.append('\n=== prof_%s (%d samples; %d exe leaves, %d exe-ret) ===' % (
            name, cnt, sum(lf.values()), sum(rf.values())))
        out.append(' top-25 functions (by leaf RIP):')
        for s, v in lf.most_common(25):
            i = bisect.bisect_right(starts, s) - 1
            e = funcs[i][1]
            out.append('   %5.1f%% %5d  func 0x%X..0x%X  (size %d)' % (100.0 * v / cnt, v, s, e, e - s))
        out.append(' top-25 functions (by ret [RSP]):')
        for s, v in rf.most_common(25):
            i = bisect.bisect_right(starts, s) - 1
            e = funcs[i][1]
            out.append('   %5.1f%% %5d  func 0x%X..0x%X  (size %d)' % (100.0 * v / cnt, v, s, e, e - s))
    txt = '\n'.join(out)
    open(r'C:\Dev\_research\prof_pdata_report.txt', 'w', encoding='utf-8').write(txt)
    print(txt)

if __name__ == '__main__':
    main()

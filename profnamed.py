# -*- coding: utf-8 -*-
# Named attribution of TickProf profiles: .bin/.ret/.wait + .pdata boundaries + names from Ghidra (PDB).
import struct, bisect, collections, glob, os, sys

TICKPROF = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi\\Plugins\_backup\\TickProf'
EXE = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ShooterGameServer.exe'
TSV = r'C:\Dev\_research\ghidra_funcs_v361.tsv'
import profanalyze as pa

TEXT_END = 0x391AA6E  # .text end (from profpdata.py)


def load_pdata():
    """.pdata functions from the exe exception directory"""
    import profpdata
    return profpdata.get_pdata(EXE), None


def load_ghidra_names():
    """[(rva_start, size, name)] from the Ghidra function dump."""
    out = []
    with open(TSV, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            p = line.rstrip('\n').split('\t')
            if len(p) == 3:
                try:
                    out.append((int(p[0], 16), int(p[2]), p[1]))
                except ValueError:
                    continue
    out.sort()
    starts = [x[0] for x in out]
    return out, starts


class Namer:
    def __init__(self, ghidra, starts):
        self.ghidra = ghidra
        self.starts = starts
        self._cache = {}

    def name(self, rva):
        if rva in self._cache:
            return self._cache[rva]
        i = bisect.bisect_right(self.starts, rva) - 1
        n = None
        if i >= 0:
            s, sz, nm = self.ghidra[i]
            if rva < s + sz:
                n = '%s+0x%x' % (nm, rva - s) if rva != s else nm
        self._cache[rva] = n
        return n


def main():
    pdata, _ = load_pdata()
    pdata_starts = [x[0] for x in pdata]
    ghidra, gstarts = load_ghidra_names()
    namer = Namer(ghidra, gstarts)
    mods, bases = pa.load_modules(TICKPROF + r'\prof_512222984.modules.txt')
    export_idx = {}
    for base, size, short, full, is_sys in mods:
        key = short.lower()
        if key not in export_idx:
            try:
                export_idx[key] = pa.ExportIndex(full)
            except Exception:
                export_idx[key] = None

    def dll_name(short, off):
        idx = export_idx.get(short.lower())
        if idx:
            nm = idx.name_of(off)
            if nm:
                return nm
        return None

    names = sys.argv[1:]
    if not names:
        names = sorted(os.path.basename(TICKPROF, ) for _ in [0])
        names = sorted({os.path.basename(p).split('_')[1].split('.')[0]
                        for p in glob.glob(TICKPROF + r'\prof_*.bin')})
    out_all = []
    for name in names:
        try:
            bdata = open(TICKPROF + r'\prof_%s.bin' % name, 'rb').read()
        except OSError:
            continue
        base_exe = struct.unpack_from('<Q', bdata, 0)[0]
        cnt = struct.unpack_from('<Q', bdata, 8)[0]
        rips = struct.unpack_from('<%dQ' % cnt, bdata, 16)
        rpath = TICKPROF + r'\prof_%s.ret' % name
        if os.path.exists(rpath):
            rdata = open(rpath, 'rb').read()
            rets = struct.unpack_from('<%dQ' % cnt, rdata)
        else:
            rets = [0] * cnt

        mod_cnt = collections.Counter()
        lf = collections.Counter()   # exe funcs by leaf
        rf = collections.Counter()   # exe funcs by ret
        dll_leaf = collections.Counter()
        exe_min_rva = 1 << 60
        wait = None
        wpath = TICKPROF + r'\prof_%s.wait' % name
        wait_stacks = []
        if os.path.exists(wpath):
            wdata = open(wpath, 'rb').read()
            wcnt = struct.unpack_from('<Q', wdata, 0)[0]
            # v2 format: hdr = [count, words_per_record]; v1: words=5, records start at byte 8
            wwords = 5
            wbase = 8
            if len(wdata) >= 16:
                w2 = struct.unpack_from('<Q', wdata, 8)[0]
                if 0 < w2 <= 32:
                    wwords = w2
                    wbase = 16
            words = struct.unpack_from('<%dQ' % (wcnt * wwords), wdata, wbase)
            wait_stacks = [words[i * wwords:(i + 1) * wwords] for i in range(wcnt)]
        for rip, ret in zip(rips, rets):
            short, off, is_sys = pa.mod_of(rip, mods, bases)[0], pa.mod_of(rip, mods, bases)[1], None
            cls = pa.mod_of(rip, mods, bases)
            short = cls[0]; off = cls[1]
            mod_cnt[short if short is not None else '<kernel/outside modules>'] += 1
            if short is None:
                continue
            if is_sys:
                nm = dll_name(short, off) or ('%s+0x%X' % (short, off))
                dll_leaf[nm] += 1
            elif short == 'ShooterGameServer.exe' and off < TEXT_END:
                exe_min_rva = min(exe_min_rva, off)
                i2 = bisect.bisect_right(pdata_starts, off) - 1
                if 0 <= i2 and off < pdata[i2][1]:
                    s0 = pdata[i2][0]
                else:
                    s0 = off
                lf[s0] += 1
            else:
                nm = dll_name(short, off) or ('%s+0x%X' % (short, off))
                dll_leaf[nm] += 1
            rcls = pa.mod_of(ret, mods, bases)
            if rcls[0] == 'ShooterGameServer.exe' and rcls[1] < TEXT_END:
                ro = rcls[1]
                i3 = bisect.bisect_right(pdata_starts, ro) - 1
                if 0 <= i3 and ro < pdata[i3][1]:
                    ro = pdata[i3][0]
                rf[ro] += 1

        out = []
        out.append('=== prof_%s: %d samples, %d wait records ===' % (name, cnt, len(wait_stacks)))
        out.append('modules (RIP leaf): ' + ', '.join('%s %d (%.1f%%)' % (k, v, 100.0 * v / cnt)
                                                     for k, v in mod_cnt.most_common(8)))
        out.append('')
        out.append('system/GUI-DLL leaves (named):')
        for k, v in dll_leaf.most_common(12):
            out.append('  %5.1f%% %5d  %s' % (100.0 * v / cnt, v, k))
        out.append('')
        out.append('top-40 exe functions (by leaf RIP):')
        for s, v in lf.most_common(40):
            nm = namer.name(s) or ('sub_%X' % s)
            out.append('  %5.1f%% %5d  rva 0x%X  %s' % (100.0 * v / cnt, v, s, nm))
        out.append('')
        out.append('top-25 exe functions (by ret [RSP], i.e. where the leaf was called from):')
        for s, v in rf.most_common(25):
            nm = namer.name(s) or ('sub_%X' % s)
            out.append('  %5.1f%% %5d  rva 0x%X  %s' % (100.0 * v / cnt, v, s, nm))
        out.append('')
        if wait_stacks:
            # parsing wait records: rip (sys-DLL, named) + stack words in exe code (call candidates)
            wrip = collections.Counter()
            exe_frame = collections.Counter()
            zero_frames = 0
            for w in wait_stacks:
                rip = w[0]
                cls = pa.mod_of(rip, mods, bases)
                nm = (dll_name(cls[0], cls[1]) if cls[0] else None) or (('%s+0x%X' % (cls[0], cls[1])) if cls[0] else 'kernel+0x%X' % rip)
                wrip[nm] += 1
                found = None
                for sv in w[1:]:
                    scls = pa.mod_of(sv, mods, bases)
                    if scls[0] == 'ShooterGameServer.exe' and scls[1] < TEXT_END:
                        found = scls[1]
                        break
                if found is None:
                    zero_frames += 1
                else:
                    i4 = bisect.bisect_right(pdata_starts, found) - 1
                    if 0 <= i4 and found < pdata[i4][1]:
                        found = pdata[i4][0]
                    exe_frame[found] += 1
            out.append('wait stacks (%d records):' % len(wait_stacks))
            out.append(' syscall sites:')
            for k, v in wrip.most_common(12):
                out.append('  %5.1f%% %5d  %s' % (100.0 * v / len(wait_stacks), v, k))
            out.append(' call candidates in the exe (code word below rip):')
            for k, v in exe_frame.most_common(12):
                nm = namer.name(k) or ('sub_%X' % k)
                out.append('  %5.1f%% %5d  rva 0x%X  %s' % (100.0 * v / len(wait_stacks), v, k, nm))
            out.append(' no exe word in the top 4 stack words: %d (%.1f%%)' %
                       (zero_frames, 100.0 * zero_frames / len(wait_stacks)))
        out_all.append('\n'.join(out))

    report = ('\n\n'.join(out_all))
    fn = r'C:\Dev\_research\prof_named_report.txt'
    with open(fn, 'w', encoding='utf-8') as f:
        f.write(report)
    print('wrote:', fn, 'profiles:', len(out_all))
    # print the first profile in full (the key one - the Genesis base)
    print(out_all[-1][:12000] if out_all else 'empty')


if __name__ == '__main__':
    main()

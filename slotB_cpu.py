# -*- coding: utf-8 -*-
# Slot B (v2): who owns 64.8% of the phase waits (ZwQueryDirectoryFileEx) and
# how the phase differs from the dense baseline in CPU composition (Blueprint VM vs octree).
import struct, collections, sys, os
sys.path.insert(0, r'C:\Dev\_research')
sys.stdout.reconfigure(encoding='utf-8')
import profanalyze as pa
import profnamed as pn

TXT = 0x391AA6E
PLUG = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi\Plugins'
ACTIVE = os.path.join(PLUG, 'TickProf')
BACK = os.path.join(PLUG, '_backup', 'TickProf')
ghidra, gstarts = pn.load_ghidra_names()
namer = pn.Namer(ghidra, gstarts)

BP = ('exec', 'ProcessContextOpcode', 'ProcessInternal', 'Invoke', 'CallFunction',
      'CopyCompleteValue', 'CopyValues', 'execLocalVariable', 'GetFunctionCallspace',
      'ProcessEvent', 'FFrame', 'Script')


def dir_for(prof):
    p = os.path.join(ACTIVE, 'prof_%s.wait' % prof)
    return ACTIVE if os.path.exists(p) else BACK


def analyse(prof, tag):
    D0 = dir_for(prof)
    mods, bases = pa.load_modules(os.path.join(D0, 'prof_%s.modules.txt' % prof))
    bd = open(os.path.join(D0, 'prof_%s.bin' % prof), 'rb').read()
    rd = open(os.path.join(D0, 'prof_%s.ret' % prof), 'rb').read()
    wd = open(os.path.join(D0, 'prof_%s.wait' % prof), 'rb').read()
    ns = len(bd) // 8
    rips = struct.unpack_from('<%dQ' % ns, bd, 0)
    nret = len(rd) // 8
    rets = struct.unpack_from('<%dQ' % nret, rd, 0)
    wcnt = struct.unpack_from('<Q', wd, 0)[0]
    ww = struct.unpack_from('<%dQ' % (wcnt * 5), wd, 8)

    def mi(a):
        return pa.mod_of(a, mods, bases)

    def exefn(a):
        s, o, _ = mi(a)
        if s == 'ShooterGameServer.exe' and o < TXT:
            return namer.name(o) or ('sub_%X' % o)
        return None

    def blocked(x):
        s, o, issys = mi(x)
        return True if s is None else bool(issys)

    pairs = []
    k = 0
    for i in range(ns):
        if blocked(rips[i]):
            if k < wcnt and ww[k * 5] == rips[i]:
                pairs.append((i, k))
                k += 1

    # --- owner of the wait: the nearest FOLLOWING exe sample (leaf) + its ret (caller)
    fileio_leaf = collections.Counter()
    fileio_caller = collections.Counter()
    other_leaf = collections.Counter()
    for (i, k) in pairs:
        s, o, _ = mi(ww[k * 5])
        is_fileio = (s == 'ntdll.dll' and o == 0x161794)
        leaf = None
        for j in range(i + 1, min(ns, i + 1 + 10)):
            f = exefn(rips[j])
            if f:
                leaf = (j, f)
                break
        if leaf is None:
            continue
        j, lf = leaf
        caller = exefn(rets[j]) if j < nret else None
        if is_fileio:
            fileio_leaf[lf] += 1
            fileio_caller[caller or '<non-exe>'] += 1
        else:
            other_leaf[lf] += 1

    # --- CPU composition: Blueprint VM share
    leaf_all = collections.Counter()
    bp_cnt = 0
    for r in rips:
        s, o, _ = mi(r)
        if s == 'ShooterGameServer.exe' and o < TXT:
            nm = namer.name(o) or ('sub_%X' % o)
            leaf_all[nm] += 1
            if any(b in nm for b in BP):
                bp_cnt += 1
    exe_tot = sum(leaf_all.values())
    print('\n########## %s (prof %s) ##########' % (tag, prof))
    print('  samples=%d, wait=%d (%.1f%%)' % (ns, wcnt, 100.0 * wcnt / ns))
    print('  CPU in exe: %d samples; Blueprint-VM functions: %d (%.1f%% of exe CPU)' % (
        exe_tot, bp_cnt, 100.0 * bp_cnt / max(1, exe_tot)))
    print('  top-12 exe leaves:')
    for nm, c in leaf_all.most_common(12):
        print('     %5d (%4.1f%%)  %s' % (c, 100.0 * c / max(1, exe_tot), nm))
    print('  file IO owner (next exe leaf after ZwQueryDirectoryFileEx):')
    for nm, c in fileio_leaf.most_common(8):
        print('     %5d  %s' % (c, nm))
    print('  its caller ([RSP] of that leaf):')
    for nm, c in fileio_caller.most_common(8):
        print('     %5d  %s' % (c, nm))
    print('  other waits: top-5 next exe leaves')
    for nm, c in other_leaf.most_common(5):
        print('     %5d  %s' % (c, nm))
    return dict(prof=prof, samples=ns, waits=wcnt, exe_cpu=exe_tot, bp_pct=100.0 * bp_cnt / max(1, exe_tot),
                top_leaf=dict(leaf_all.most_common(15)),
                fileio_leaf=dict(fileio_leaf.most_common(10)),
                fileio_caller=dict(fileio_caller.most_common(10)))


if __name__ == '__main__':
    out = []
    out.append(analyse('631247234', 'SLOT B: PHASE 21.10 21:57 (t/s 28-33)'))
    out.append(analyse('512222984', 'SLOT A: dense baseline 20.10 12:53 (t/s 21)'))
    out.append(analyse('301269000', 'idle: empty world (Sleep pacing)'))
    import json
    with open(r'C:\Dev\_research\slotB\compare_cpu.json', 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('\nsaved: slotB/compare_cpu.json')

# -*- coding: utf-8 -*-
# Слот A: перечисление call-site'ов WaitForSingleObject* в exe (через IAT)
# и обратных вызовов для ключевых функций taskgraph.
import struct, sys, collections, time
sys.stdout.reconfigure(encoding='utf-8')

EXE = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ShooterGameServer.exe'
D = open(EXE, 'rb').read()
pe = struct.unpack_from('<I', D, 0x3C)[0]
nsec = struct.unpack_from('<H', D, pe + 6)[0]
opt_size = struct.unpack_from('<H', D, pe + 20)[0]
so = pe + 24 + opt_size
secs = []
for i in range(nsec):
    s = so + i * 40
    nm = D[s:s + 8].split(b'\0')[0].decode('ascii', 'replace')
    vsize = struct.unpack_from('<I', D, s + 8)[0]
    vaddr = struct.unpack_from('<I', D, s + 12)[0]
    rawsize = struct.unpack_from('<I', D, s + 16)[0]
    rawptr = struct.unpack_from('<I', D, s + 20)[0]
    secs.append((nm, vaddr, vsize, rawptr, rawsize))
SEC = {x[0]: x for x in secs}
nm, tva, tvs, trp, trs = SEC['.text']
body = D[trp:trp + min(tvs, trs)]
n = len(body)
IMAGEBASE = 0x140000000

import profnamed as pn
ghidra, gstarts = pn.load_ghidra_names()
namer = pn.Namer(ghidra, gstarts)
FUNCS = [(s, sz, nm_) for (s, sz, nm_) in ghidra]


def func_of(rva):
    return namer.name(rva) or ('sub_%X' % rva)


def func_start(rva):
    import bisect
    i = bisect.bisect_right(gstarts, rva) - 1
    if i >= 0:
        s, sz, nm_ = FUNCS[i]
        if rva < s + sz:
            return s, nm_
    return None, None


# --- импорты: ищем IAT KERNELBASE!WaitForSingleObjectEx ---
def rva2off(rva):
    for nmm, va, vs, rp, rs in secs:
        if va <= rva < va + max(vs, rs):
            return rp + (rva - va)
    return None


def parse_imports():
    opt = pe + 24
    dirs = opt + 112
    imp_rva, imp_size = struct.unpack_from('<II', D, dirs + 8)
    out = {}
    off = rva2off(imp_rva)
    while True:
        ilt, ts, fwd, name_rva, iat_rva = struct.unpack_from('<IIIII', D, off)
        if name_rva == 0:
            break
        noff = rva2off(name_rva)
        dll = D[noff:D.index(b'\0', noff)].decode('ascii', 'replace')
        t = rva2off(ilt if ilt else iat_rva)
        i = 0
        while True:
            v = struct.unpack_from('<Q', D, t + i * 8)[0]
            if v == 0:
                break
            if not (v >> 63):
                noff = rva2off((v & 0x7FFFFFFF) + 2)  # +2: IMAGE_IMPORT_BY_NAME.Hint
                fn = D[noff:D.index(b'\0', noff)].decode('ascii', 'replace')
            else:
                fn = '#ord%d' % (v & 0xFFFF)
            out[(dll.lower(), fn.lower())] = iat_rva + i * 8
            i += 1
        off += 20
    return out


imports = parse_imports()
print('импортов: %d' % len(imports))
targets = {}
for (dll, fn), iat in imports.items():
    if ('wait' in fn or fn in ('sleep', 'sleepex')) and not fn.startswith('__real'):
        targets[(dll, fn)] = iat
for k, v in sorted(targets.items()):
    print('   IAT %-14s %-24s rva 0x%X' % (k[0], k[1], v))

# --- ищем call [rip+disp] на эти IAT ---
print('\n=== call-site\'ы (FF 15) на WaitForSingleObject* ===')
found = collections.defaultdict(list)
for i in range(n - 6):
    if body[i] == 0xFF and body[i + 1] == 0x15:
        disp = struct.unpack_from('<i', body, i + 2)[0]
        tgt = tva + i + 6 + disp
        for k, iat in targets.items():
            if tgt == iat:
                found[k].append(tva + i)

for k, lst in found.items():
    print('\n%s!%s : %d call-site\'ов' % (k[0], k[1], len(lst)))
    byfn = collections.Counter()
    for cs in lst:
        fs, fn = func_start(cs)
        byfn[(fs, fn)] += 1
    for (fs, fn), c in byfn.most_common(40):
        print('   %4d  rva 0x%s  %s' % (c, ('%X' % fs) if fs else '?', fn or '?'))

# --- обратные вызовы: кто зовёт заданные функции ---
def callers_of(target_rva):
    out = []
    for i in range(n - 5):
        if body[i] == 0xE8:
            disp = struct.unpack_from('<i', body, i + 1)[0]
            if tva + i + 5 + disp == target_rva:
                out.append(tva + i)
    return out


print('\n=== обратные вызовы ===')
for name_frag in ('ProcessTasksNamedThread', 'Stall', 'FEvent::Wait', 'WaitForTask'):
    cands = [s for (s, sz, nm_) in FUNCS if nm_ and name_frag in nm_]
    for s in cands[:6]:
        cl = callers_of(s)
        byfn = collections.Counter()
        for cs in cl:
            fs, fn = func_start(cs)
            byfn[(fs, fn)] += 1
        print('\n%s @0x%X : %d callers' % (namer.name(s), s, len(cl)))
        for (fs, fn), c in byfn.most_common(8):
            print('     %4d  %s' % (c, fn or '?'))

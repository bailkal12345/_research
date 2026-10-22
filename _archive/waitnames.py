# -*- coding: utf-8 -*-
# Слот A (v5): имена syscall'ов ожидания (экспорты ntdll) + PDB-строки для
# call-site'ов WaitForSingleObject в exe => именованная атрибуция.
import struct, collections, sys
sys.stdout.reconfigure(encoding='utf-8')

TICKPROF = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi\Plugins\_backup\TickProf'
import profanalyze as pa
import profnamed as pn
import pdbsym

# --- экспорты ntdll из System32 ---
NTDLL = r'C:\Windows\System32\ntdll.dll'
D = open(NTDLL, 'rb').read()
pe = struct.unpack_from('<I', D, 0x3C)[0]
opt = pe + 24
dirs = opt + 112
exp_rva, exp_size = struct.unpack_from('<II', D, dirs)
secs = []
nsec = struct.unpack_from('<H', D, pe + 6)[0]
opt_size = struct.unpack_from('<H', D, pe + 20)[0]
so = pe + 24 + opt_size
for i in range(nsec):
    s = so + i * 40
    nm = D[s:s + 8].split(b'\0')[0].decode('ascii', 'replace')
    vsize = struct.unpack_from('<I', D, s + 8)[0]
    vaddr = struct.unpack_from('<I', D, s + 12)[0]
    rawsize = struct.unpack_from('<I', D, s + 16)[0]
    rawptr = struct.unpack_from('<I', D, s + 20)[0]
    secs.append((nm, vaddr, vsize, rawptr, rawsize))


def r2o(rva):
    for nm, va, vs, rp, rs in secs:
        if va <= rva < va + max(vs, rs):
            return rp + (rva - va)
    return None


eo = r2o(exp_rva)
nnames = struct.unpack_from('<I', D, eo + 24)[0]
afun = struct.unpack_from('<I', D, eo + 28)[0]
anames = struct.unpack_from('<I', D, eo + 32)[0]
aords = struct.unpack_from('<I', D, eo + 36)[0]
epl = []
for i in range(nnames):
    rva = struct.unpack_from('<I', D, r2o(afun) + 4 * i)[0]
    no = r2o(anames) + struct.unpack_from('<I', D, r2o(aords) + 4 * i)[0]
    if no is None:
        continue
    end = D.find(b'\0', no)
    if end < 0:
        continue
    nm = D[no:end].decode('ascii', 'replace')
    epl.append((rva, nm))
epl.sort()
exp_names = [n for _, n in epl]
exp_rvas = [r for r, _ in epl]


def ntdll_name(rva):
    import bisect
    i = bisect.bisect_right(exp_rvas, rva) - 1
    if i >= 0:
        return '%s+0x%x' % (exp_names[i], rva - exp_rvas[i])
    return 'rva 0x%x' % rva


# --- профиль: syscall-имена ---
mods, bases = pa.load_modules(TICKPROF + r'\prof_512222984.modules.txt')
ntdll_base = None
for base, size, short, full, issys in mods:
    if short.lower() == 'ntdll.dll':
        ntdll_base = base
print('ntdll base = 0x%X' % ntdll_base)

d = open(TICKPROF + r'\prof_512222984.wait', 'rb').read()
n = struct.unpack_from('<Q', d, 0)[0]
ws = struct.unpack_from('<%dQ' % (n * 5), d, 8)
cnt = collections.Counter()
for i in range(n):
    rip = ws[i * 5]
    short, off, _ = pa.mod_of(rip, mods, bases)
    if short == 'ntdll.dll':
        cnt[ntdll_name(off)] += 1
    else:
        cnt['%s+0x%x' % (short or 'raw', off or 0)] += 1
print('\n=== syscall-имена (ntdll) в 762 wait-записях ===')
for k, v in cnt.most_common(14):
    print('  %5d (%5.1f%%)  %s' % (v, 100.0 * v / n, k))

# --- PDB-строки для call-site'ов WaitForSingleObject в exe ---
print('\n=== PDB-строки exe для мест ожидания (WaitForSingleObject call-sites + FEvent::Wait) ===')
import callsites_all as cs
targets = {k: v for k, v in cs.targets.items() if 'waitfor' in k[1]}
for (dll, fn), iat in targets.items():
    lst = cs.found.get((dll, fn), [])
    print('\n%s!%s : %d call-site\'ов' % (dll, fn, len(lst)))
    seen = set()
    for site in lst:
        fs, fname = cs.func_start(site)
        key = fname
        ret_rva = site + 6  # FF 15 = 6 байт
        fn_, ln_ = pdbsym.resolve_lines(ret_rva)
        sig = '%s  @0x%X  -> %s' % (fname, site, ('%s:%s' % (fn_.split('\\')[-1] if fn_ else '?', ln_)) if fn_ else '?')
        if sig in seen:
            continue
        seen.add(sig)
        print('   ', sig)

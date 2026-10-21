# -*- coding: utf-8 -*-
# Владелец ZwQueryDirectoryFileEx (64.8% ожиданий в профиле фазы):
# ищем call-site'ы FindFirstFileW/FindNextFileW в exe + имена/исходники.
import struct, collections, sys
sys.path.insert(0, r'C:\Dev\_research')
sys.stdout.reconfigure(encoding='utf-8')
import callsites_all as cs
import pdbsym

D = open(cs.EXE, 'rb').read()
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
nm, tva, tvs, trp, trs = [x for x in secs if x[0] == '.text'][0]
body = D[trp:trp + min(tvs, trs)]

want = {k: v for k, v in cs.imports.items() if k[1] in ('findfirstfilew', 'findnextfilew', 'findclose')}
print('=== IAT ===')
for k, v in want.items():
    print('   %s!%s  rva 0x%X' % (k[0], k[1], v))

print('\n=== call-site\'ы (FF 15) ===')
for i in range(len(body) - 6):
    if body[i] == 0xFF and body[i + 1] == 0x15:
        disp = struct.unpack_from('<i', body, i + 2)[0]
        tgt = tva + i + 6 + disp
        for k, v in want.items():
            if tgt == v:
                site = tva + i
                fs, fname = cs.func_start(site)
                ret = site + 6
                f_, l_ = pdbsym.resolve_lines(ret)
                src = ('%s:%s' % (f_.replace('d:\\ase\\engine\\source\\', '').replace('\\', '/'), l_)) if f_ else '?'
                print('   %-16s site 0x%X  fn=%-38s %s' % (k[1], site, fname or '?', src))

print('\n=== кто ещё зовёт эти IAT (косвенно, через register) ===')
# грубая эвристика: ищем MOV reg,[rip+IAT] для этих адресов
for k, v in want.items():
    tgt_rva = v
    hits = []
    for i in range(len(body) - 7):
        if body[i] in (0x48, 0x4C) and body[i + 1] == 0x8B and (body[i + 2] & 0xC7) == 0x05:
            disp = struct.unpack_from('<i', body, i + 3)[0]
            if tva + i + 7 + disp == tgt_rva:
                fs, fname = cs.func_start(tva + i)
                hits.append((tva + i, fname))
    print('   %-16s MOV-ссылок: %d' % (k[1], len(hits)))
    for r, fn_ in hits[:12]:
        print('        0x%X  %s' % (r, fn_ or '?'))

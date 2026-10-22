# -*- coding: utf-8 -*-
# Слот A (v8): имена + исходники (PDB) для всех мест ожидания в exe.
# 1) 20 call-site'ов kernel32!WaitForSingleObject (+1 WaitForMultipleObjects)
# 2) вызывающие их функции -> кто в движке ждёт
import sys, collections
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'C:\Dev\_research')
import callsites_all as cs
import pdbsym

for (dll, fn), iat in sorted(cs.targets.items()):
    if 'waitfor' not in fn:
        continue
    lst = cs.found.get((dll, fn), [])
    print('\n===== %s!%s : %d call-site\'ов (IAT 0x%X) =====' % (dll, fn, len(lst), iat))
    for site in sorted(lst):
        fs, fname = cs.func_start(site)
        ret = site + 6
        nm, disp, sz = pdbsym.resolve(ret)
        f_, l_ = pdbsym.resolve_lines(ret)
        src = ('%s:%s' % (f_.replace('d:\\ase\\engine\\source\\', '').replace('\\', '/') if f_ else '?', l_)) if f_ else '?'
        print('  site 0x%X  fn=%-38s ret@0x%X -> %s' % (site, fname or '?', ret, src))
        # вызывающие site
        callers = cs.callers_of(site)
        byfn = collections.Counter()
        for c in callers:
            s2, f2 = cs.func_start(c)
            byfn[(s2, f2)] += 1
        for (s2, f2), cnt in byfn.most_common(6):
            l2 = pdbsym.resolve_lines(c + 5)
            s2src = ('%s:%s' % (l2[0].replace('d:\\ase\\engine\\source\\', '').replace('\\', '/') if l2[0] else '?', l2[1])) if l2[0] else '?'
            print('        <- %-36s %s' % (f2 or '?', s2src))

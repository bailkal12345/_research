# -*- coding: utf-8 -*-
# Outline of TickProf.cpp: section markers + function definitions with lengths.
import io
import re

p = r'C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp'
lines = io.open(p, encoding='utf-8').read().splitlines()

fn_re = re.compile(r'^\t(?:static\s+)?[\w:<>~*&\s]+?\b(\w+)\s*\([^;]*?\)\s*(?:const)?\s*\{?\s*$')
cur = None
start = 0
out = []
for i, l in enumerate(lines, 1):
    s = l.strip()
    m = fn_re.match(l)
    sec = re.match(r'^\t?//-* ?(.+?)\s*-*\s*$', s) if s.startswith('//') and set(s) - set('/- ') else None
    if sec and len(s) > 8:
        pass
    if m and not s.startswith('//') and '=' not in s.split('(')[0]:
        if cur:
            out.append((cur, start, i - 1))
        cur = m.group(1)
        start = i
if cur:
    out.append((cur, start, len(lines)))

out = [(n, a, b, b - a + 1) for n, a, b, *_ in out]
print('functions: %d, total lines %d' % (len(out), len(lines)))
for n, a, b, sz in out:
    print('%-42s %5d..%5d  %4d' % (n, a, b, sz))

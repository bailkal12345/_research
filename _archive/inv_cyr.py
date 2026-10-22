# -*- coding: utf-8 -*-
# Inventory of Cyrillic string literals and comments in TickProf.cpp.
import collections
import io
import re

p = r'C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp'
s = io.open(p, encoding='utf-8', errors='replace').read()

lits = re.findall(r'"((?:[^"\\]|\\.)*[\u0400-\u04FF](?:[^"\\]|\\.)*)"', s, re.S)
seen = collections.Counter()
for l in lits:
    seen[l] += 1
print('=== STRING LITERALS WITH CYRILLIC: %d (unique: %d) ===' % (len(lits), len(seen)))
for l, n in seen.most_common():
    print('%d x %s' % (n, l if len(l) < 160 else l[:157] + '...'))
print()
print('=== COMMENTS WITH CYRILLIC (unique) ===')
cm = collections.Counter()
for m in re.finditer(r'//[^\r\n]*[\u0400-\u04FF][^\r\n]*', s):
    t = m.group(0).strip()
    cm[t] += 1
print('unique: %d' % len(cm))
for t, n in cm.most_common():
    print('%d x %s' % (n, t if len(t) < 170 else t[:167] + '...'))

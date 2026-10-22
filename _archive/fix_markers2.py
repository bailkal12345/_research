# -*- coding: utf-8 -*-
# Pass 2: regex variants with escaped dot/backslash-d that pass 1 missed.
import glob
import io
import os
import re

REPL = [
    ('save: запись \\.ark завершилась, длительность (\\d+) мс',
     'save: \\.ark write finished, duration (\\d+) ms'),
    ('контаминировано сохранением мира, (\\d+) из (\\d+) кадров',
     'contaminated by a world save, (\\d+) of (\\d+) frames'),
]

import py_compile
bad = []
for p in glob.glob(r'C:\Dev\_research\*.py'):
    base = os.path.basename(p)
    if base.startswith(('fix_', 'inv_')):
        continue
    s = io.open(p, encoding='utf-8', newline='').read()
    n = 0
    for old, new in REPL:
        if old in s:
            n += s.count(old)
            s = s.replace(old, new)
    if n:
        io.open(p, 'w', encoding='utf-8', newline='').write(s)
        print('%-22s replacements=%d' % (base, n))
        try:
            py_compile.compile(p, doraise=True)
        except Exception as e:
            bad.append((base, e))
print('compile failures:', bad if bad else 'none')

# -*- coding: utf-8 -*-
# Pass 3: replace the remaining dead Russian log-matchers with English plugin strings.
import io

REPL = [
    # slotD_ab2.py
    ("'контаминировано' in l", "'contaminated' in l"),
    ('"контаминировано" in l', '"contaminated" in l'),
    # slotE_matrix.py
    ("'скриптовых' in out", "'enumeration' in out"),
    ('"скриптовых" in out', '"enumeration" in out'),
    ("'ПО SELF-ВРЕМЕНИ' in l", "'TOP-20 BY SELF TIME' in l"),
    ('"ПО SELF-ВРЕМЕНИ" in l', '"TOP-20 BY SELF TIME" in l'),
    ("'сумма' in first", "'self sum' in first"),
    ('"сумма" in first', '"self sum" in first'),
    ("r'actors?=\\d+|компонент|components?'", "r'owners=|components='"),
    # slotE_measure.py
    ("r'акторы?=\\d+|актор(ов)?=|компонент|components?'", "r'owners=|components='"),
    # monparse.py
    ('save: начало записи \\.ark', 'save: .ark write started'),
    # slotC_ab.py overlaptrim regex -> English, keep 3 capture groups
    ("r'overlaptrim3?: порог=(\\d+) отключено компонентов=(\\d+) освобождено записей=(\\d+)'",
     "r'overlaptrim3?: threshold=(\\d+) .*?disabled=(\\d+).*?entries freed=(\\d+)'"),
]

FILES = [r'C:\Dev\_research\slotD_ab2.py', r'C:\Dev\_research\slotE_matrix.py',
         r'C:\Dev\_research\slotE_measure.py', r'C:\Dev\_research\monparse.py',
         r'C:\Dev\_research\slotC_ab.py']

import py_compile
for p in FILES:
    s = io.open(p, encoding='utf-8', newline='').read()
    n = 0
    for old, new in REPL:
        if old in s:
            n += s.count(old)
            s = s.replace(old, new)
    io.open(p, 'w', encoding='utf-8', newline='').write(s)
    py_compile.compile(p, doraise=True)
    print('%s: %d replacements, compiles OK' % (p.split('\\')[-1], n))

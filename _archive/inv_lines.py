# -*- coding: utf-8 -*-
# Dump all Cyrillic-containing lines of TickProf.cpp with line numbers.
import io

p = r'C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp'
out = io.open(r'C:\Dev\_research\inv_lines.txt', 'w', encoding='utf-8')
with io.open(p, encoding='utf-8', errors='replace') as f:
    for i, l in enumerate(f, 1):
        if any('\u0400' <= c <= '\u04ff' for c in l):
            out.write('%d: %s' % (i, l))
out.close()
print('done')

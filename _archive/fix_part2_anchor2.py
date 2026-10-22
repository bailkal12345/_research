# -*- coding: utf-8 -*-
# Точечная правка fix_bptrace_v2_part2.py: вставка CooldownStart после строки
# "wait_path));" (идёт сразу за "ожидание в syscall").
import io
import re

P = r'C:\Dev\_research\fix_bptrace_v2_part2.py'
p = io.open(P, 'r', encoding='utf-8', newline='').read()

start = p.index('src = insert_after(')
end = p.index(', src)', start) + len(', src)')
new_block = ("src = insert_after(blk('''\t\t\twait_path));'''), blk('''\n\t\tCooldownStart(\"окно сэмплирования\");'''), src)")
p = p[:start] + new_block + p[end:]
io.open(P, 'w', encoding='utf-8', newline='').write(p)

# проверка: реальные отступы в исходнике
CPP = r'C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp'
src = io.open(CPP, 'r', encoding='utf-8', newline='').read()
i = src.index('ожидание в syscall')
seg = src[i - 60:i + 200]
for line in seg.split('\n'):
    print(repr(line[:120]))

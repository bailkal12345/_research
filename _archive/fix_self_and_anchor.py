# -*- coding: utf-8 -*-
# 1) переименовать локальную переменную self (конфликт с параметром обработчика);
# 2) починить якорь WriteResults в fix_bptrace_v2_part2.py.
import io

CPP = r'C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp'
src = io.open(CPP, 'r', encoding='utf-8', newline='').read()
src = src.replace('const uint64_t self = total - f.children;', 'const uint64_t self_ticks = total - f.children;')
src = src.replace('InterlockedExchangeAdd64(&s.self_ticks, (LONG64)self);',
                  'InterlockedExchangeAdd64(&s.self_ticks, (LONG64)self_ticks);')
io.open(CPP, 'w', encoding='utf-8', newline='').write(src)
print('исходник: self -> self_ticks')

P = r'C:\Dev\_research\fix_bptrace_v2_part2.py'
p = io.open(P, 'r', encoding='utf-8', newline='').read()
old = """src = insert_after('''\t\tLogLine(S("ожидание в syscall: {}/{} сэмплов ({}%), файл {}", wc, tc, share,
\t\t\twait_path));''', blk('''\t\tCooldownStart("окно сэмплирования");'''), src)"""
new = """src = insert_after(blk('''\t\tLogLine(S("ожидание в syscall: {}/{} сэмплов ({}%), файл {}", wc, tc, share,
\t\t\twait_path));'''), blk('''\t\tCooldownStart("окно сэмплирования");'''), src)"""
if old in p:
    p = p.replace(old, new)
else:
    # запасной путь: заменить по началу строки
    i = p.index("src = insert_after('''\t\tLogLine(S(\"ожидание в syscall:")
    j = p.index("), src)", i) + len("), src)")
    p = p[:i] + "src = insert_after(blk('''\t\tLogLine(S(\"ожидание в syscall: {}/{} сэмплов ({}%), файл {}\", wc, tc, share,\n\t\t\twait_path));'''), blk('''\t\tCooldownStart(\"окно сэмплирования\");'''), src)" + p[j:]
io.open(P, 'w', encoding='utf-8', newline='').write(p)
print('part2: якорь WriteResults поправлен')

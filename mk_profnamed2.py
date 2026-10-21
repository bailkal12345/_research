# -*- coding: utf-8 -*-
# Копия profnamed.py с параметризуемой модульной картой (нужно для профилей,
# снятых при разных базах загрузки exe - ASLR меняет базу между сессиями).
import io

s = io.open(r'C:\Dev\_research\profnamed.py', encoding='utf-8').read()
old = "mods, bases = pa.load_modules(TICKPROF + r'\\prof_512222984.modules.txt')"
new = ("import os as _os\n"
       "    _prof = _os.environ.get('PROF_NAME', '512222984')\n"
       "    mods, bases = pa.load_modules(TICKPROF + r'\\prof_%s.modules.txt' % _prof)")
assert old in s, 'строка загрузки modules.txt не найдена'
s = s.replace(old, new, 1)
io.open(r'C:\Dev\_research\profnamed2.py', 'w', encoding='utf-8', newline='').write(s)
print('profnamed2.py создан')

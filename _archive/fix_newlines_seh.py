# -*- coding: utf-8 -*-
# 1) Чистка размноженных переводов строк (артефакт blk() на тексте из файла).
# 2) Убираем __try (C2712: нельзя в функции с объектами, требующими раскрутки) -
#    путь через GetObjectsOfClass безопасен сам по себе.
import io

CPP = r'C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp'
src = io.open(CPP, 'r', encoding='utf-8', newline='').read()

before = src.count('\r\n\r\n')
src = src.replace('\r\n\r\n', '\r\n')
after = src.count('\r\n\r\n')
print('убрано двойных CRLF: %d -> %d' % (before, after))

# 3) вычищаем SEH-блоки (оставляем безопасный путь через API движка)
import re
src = re.sub(r'\t*__try\r\n', '', src)
src = re.sub(r'\t*__except \(EXCEPTION_EXECUTE_HANDLER\)\r\n', '', src)
src = re.sub(r'\t*\{\r\n\t*continue;\r\n\t*\}\r\n', '', src)
src = re.sub(r'\t*\{\r\n\t*res\.error = "[^"]*";\r\n\t*return res;\r\n\t*\}\r\n', '', src)
src = re.sub(r'\t*res\.error = "[^"]*";\r\n', '', src)
src = re.sub(r'\t*g_bp_targets\.pop_back\(\);\r\n', '', src)
src = re.sub(r'\t*g_bp_orig_func\.pop_back\(\);\r\n', '', src)

io.open(CPP, 'w', encoding='utf-8', newline='').write(src)
print('SEH-блоки удалены, переводы нормализованы')

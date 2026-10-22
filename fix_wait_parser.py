# -*- coding: utf-8 -*-
# Обновление офлайн-парсеров .wait: поддержка v2 (заголовок [count, words_per_record]).
import io


NEW_LOAD = '''            wdata = open(wpath, 'rb').read()
            wcnt = struct.unpack_from('<Q', wdata, 0)[0]
            # формат v2: hdr = [count, words_per_record]; v1: words=5, записи с 8-го байта
            wwords = 5
            wbase = 8
            if len(wdata) >= 16:
                w2 = struct.unpack_from('<Q', wdata, 8)[0]
                if 0 < w2 <= 32:
                    wwords = w2
                    wbase = 16
            words = struct.unpack_from('<%dQ' % (wcnt * wwords), wdata, wbase)
            wait_stacks = [words[i * wwords:(i + 1) * wwords] for i in range(wcnt)]'''

for path in (r'C:\Dev\_research\profnamed2.py', r'C:\Dev\_research\profnamed.py'):
    src = io.open(path, 'r', encoding='utf-8', newline='').read()
    nl = '\r\n' if '\r\n' in src else '\n'
    i = src.index("wdata = open(wpath, 'rb').read()")
    # граница: до строки с wait_stacks = ...
    j = src.index('wait_stacks = [', i)
    j = src.index('\n', j) + 1
    indent = src[i:src.index('wdata', i)]
    block = src[i:j]
    new = NEW_LOAD.replace('\n', nl).replace('            ', indent) + ' '
    # склеим окно i..j с новой вершиной: сохраняем предшествующий отступ строки wait-блока
    src = src[:i] + new[nl and len(nl) or 0:] + src[j:]
    # last join cleanup: ensure block doesn't duplicate trailing newline
    io.open(path, 'w', encoding='utf-8', newline='').write(src)
    print('обновлён', path)

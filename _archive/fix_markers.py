# -*- coding: utf-8 -*-
# Update log-marker strings in active analysis scripts to match the now-English
# TickProf plugin messages. Logic untouched.
import glob
import io
import os

REPL = [
    ('window окно:', 'window result:'),
    ('save: запись .ark завершилась, длительность (\\d+) мс',
     'save: .ark write finished, duration (\\d+) ms'),
    ('save: запись .ark завершилась', 'save: .ark write finished'),
    ('bptrace: включён', 'bptrace: v2 enabled'),
    ('bptrace: выключен', 'bptrace: disabled'),
    ('bptrace: перечисление', 'bptrace: enumeration'),
    ('сумма self', 'self sum'),
    ('вызовов всего', 'total calls'),
    ('сэмплирование завершено', 'sampler stopped'),
    ('Значение лимита', 'N/A'),
    # verdict words, in case any script echoes them back
    ('БЕЗОПАСНО-для-троттлинга', 'SAFE-for-throttling'),
    ('ЗАПРЕЩЕНО-для-троттлинга', 'FORBIDDEN-for-throttling'),
    ('мс/тик', 'ms/tick'),
]

FILES = [r'C:\Dev\_research\slotB_cpu.py',
         r'C:\Dev\_research\slotB_analyse.py',
         r'C:\Dev\_research\slotB_fileowner.py',
         r'C:\Dev\_research\slotB_fileio.py',
         r'C:\Dev\_research\slotB_monitor.py',
         r'C:\Dev\_research\slotB_octree.py',
         r'C:\Dev\_research\slotB_run.py',
         r'C:\Dev\_research\slotC_ab.py',
         r'C:\Dev\_research\slotC_analyse.py',
         r'C:\Dev\_research\slotC_control.py',
         r'C:\Dev\_research\slotC_phaseaware.py',
         r'C:\Dev\_research\slotC_quality.py',
         r'C:\Dev\_research\slotD_ab.py',
         r'C:\Dev\_research\slotD_ab2.py',
         r'C:\Dev\_research\slotD_ab_parse.py',
         r'C:\Dev\_research\slotD_fileio.py',
         r'C:\Dev\_research\slotD_fileseq.py',
         r'C:\Dev\_research\slotE_ab.py',
         r'C:\Dev\_research\slotE_matrix.py',
         r'C:\Dev\_research\slotE_measure.py',
         r'C:\Dev\_research\monparse.py',
         r'C:\Dev\_research\manual.py',
         r'C:\Dev\_research\threadcpu.py',
         r'C:\Dev\_research\a2s2.py',
         r'C:\Dev\_research\rcon.py',
         r'C:\Dev\_research\rcon3.py',
         r'C:\Dev\_research\stand_start.py',
         r'C:\Dev\_research\stand_config.py',
         r'C:\Dev\_research\stop_server.py',
         r'C:\Dev\_research\wait_port.py',
         r'C:\Dev\_research\wait_ready.py']

for p in FILES:
    if not os.path.exists(p):
        print('MISSING FILE', p)
        continue
    s = io.open(p, encoding='utf-8', newline='').read()
    n = 0
    for old, new in REPL:
        if old in s:
            n += s.count(old)
            s = s.replace(old, new)
    nl = '\r\n' if '\r\n' in s else '\n'
    io.open(p, 'w', encoding='utf-8', newline='').write(s)
    print('%-22s replacements=%d' % (os.path.basename(p), n))

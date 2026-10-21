# -*- coding: utf-8 -*-
"""Статистика окна mon для кросс-чека плагин/внешний замер.

    python analyze_g02.py HH:MM HL:MM   # границы окна включительно
"""
import re
import statistics as st
import sys

LG = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi\Plugins\TickProf\TickProf.log'
PAT = re.compile(
    r'^(\d{2}:\d{2}:\d{2})\.\d+ mon: t/s=(\d+) ms/tick=([\d.]+) '
    r'frame_ms=([\d.]+) busy=([\d.]+)% save=(\w+)')

lo, hi = sys.argv[1] if len(sys.argv) > 2 else '07:57:31', None
hi = sys.argv[2] if len(sys.argv) > 2 else '08:02:00'

rows = []
for line in open(LG, encoding='utf-8', errors='replace'):
    m = PAT.match(line)
    if m and lo <= m.group(1) <= hi:
        rows.append((int(m.group(2)), float(m.group(3)),
                     float(m.group(4)), float(m.group(5)), m.group(6)))
if not rows:
    print('строк 0 в окне %s..%s' % (lo, hi))
    raise SystemExit(1)
ts = [r[0] for r in rows]
mt = [r[1] for r in rows]
fr = [r[2] for r in rows]
bu = [r[3] for r in rows]
print('строк:', len(rows), ' окно:', rows[0][0], '..', rows[-1][0])
print('t/s: min=%d avg=%.1f max=%d' % (min(ts), st.mean(ts), max(ts)))
print('frame: avg=%.1f мс' % st.mean(fr))
print('busy (плагин): avg=%.0f%% min=%.0f%% max=%.0f%%' % (st.mean(bu), min(bu), max(bu)))
print('ms/tick (плагин): avg=%.1f' % st.mean(mt))

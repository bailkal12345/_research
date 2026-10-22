# -*- coding: utf-8 -*-
# Parse the A/B series straight from the plugin log (more reliable than parsing the driver's stdout):
# recovers the "base reset -> trim -> window -> report" sequence,
# matches each arm with its trim variant and prints a table + a per-pair summary.
import re
import sys

sys.path.insert(0, r'C:\Dev\_research')
from tputils import PLUGIN_LOG as LOG
NUM = re.compile(r'window result: t/s=([\d.]+) cpu=([\d.]+)s ms/tick=([\d.]+) frame_ms=([\d.]+) '
                  r'busy=([\d.]+)% save=(\w+) (VALID|CONTAMINATED)')
CONT = re.compile(r'window result: contaminated by a world save, (\d+) of (\d+) frames')


def main():
    lines = open(LOG, 'r', encoding='utf-8', errors='replace').read().splitlines()
    # only fresh lines today after 14:20
    start_idx = 0
    for i, l in enumerate(lines):
        if '14:20:50' in l:
            start_idx = i
            break
    seq = []
    cur_trim = None
    for l in lines[start_idx:]:
        if 'overlapall:' in l:
            cur_trim = None
        elif 'overlaptrim:' in l and 'overlaptrim3' not in l:
            cur_trim = 'trim2'
        elif 'overlaptrim3:' in l:
            cur_trim = 'trim3'
        m = NUM.search(l)
        if m:
            seq.append({'trim': cur_trim, 'tps': float(m.group(1)), 'cpu': float(m.group(2)),
                        'ms': float(m.group(3)), 'frame': float(m.group(4)), 'busy': float(m.group(5)),
                        'save': m.group(6), 'valid': m.group(7), 'raw': l.strip()})
        c = CONT.search(l)
        if c and seq:
            seq[-1]['dirty_frames'] = int(c.group(1))
            seq[-1]['frames_total'] = int(c.group(2))
    print('=== series windows (from the log) ===')
    for i, s in enumerate(seq):
        print('%2d %-6s t/s=%-6s ms/tick=%-6s busy=%-6s save=%-7s %s %s' %
              (i + 1, s['trim'], s['tps'], s['ms'], s['busy'], s['save'], s['valid'],
               ('dirty frames %s of %s' % (s.get('dirty_frames'), s.get('frames_total')))
               if 'dirty_frames' in s else ''))

    print('\n=== pairs (A=trim2, B=trim3) ===')
    pairs = []
    i = 0
    while i + 1 < len(seq):
        a, b = seq[i], seq[i + 1]
        if a['trim'] == 'trim2' and b['trim'] == 'trim3':
            pairs.append((a, b))
            i += 2
        else:
            i += 1
    deltas = []
    for n, (a, b) in enumerate(pairs, 1):
        ok = a['valid'] == 'VALID' and b['valid'] == 'VALID'
        dt = b['tps'] - a['tps']
        dm = b['ms'] - a['ms']
        print('pair %d: A t/s=%-6s ms/tick=%-6s %s | B t/s=%-6s ms/tick=%-6s %s | d(t/s)=%+.2f d(ms/tick)=%+.2f %s'
              % (n, a['tps'], a['ms'], a['valid'], b['tps'], b['ms'], b['valid'], dt, dm,
                 'ACCEPTED' if ok else 'not accepted (window invalid)'))
        if ok:
            deltas.append((dt, dm))
    if deltas:
        dts = sorted(d[0] for d in deltas)
        dms = sorted(d[1] for d in deltas)
        n = len(deltas)
        med = lambda v: v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2
        print('\naccepted pairs: %d' % n)
        print('d(t/s):      min %+.2f, median %+.2f, max %+.2f' % (dts[0], med(dts), dts[-1]))
        print('d(ms/tick):  min %+.2f, median %+.2f, max %+.2f' % (dms[0], med(dms), dms[-1]))


if __name__ == '__main__':
    main()

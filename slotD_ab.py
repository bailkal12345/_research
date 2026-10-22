# -*- coding: utf-8 -*-
# A/B series: overlaptrim 2 vs overlaptrim3, 3 pairs, shared base, 300 s window.
#
# Protocol (as in slot C, but with repeated pairs):
#   each arm: overlapall 0 (base reset) -> pause -> its own trim -> pause ->
#             300 s window -> parse the "window result:" line from the log.
#   The base reset is mandatory: otherwise arm B is measured on top of the
#   state trimmed by arm A (the slot C error).
import json
import os
import re
import sys
import time

sys.path.insert(0, r'C:\Dev\_research')
os.environ.setdefault('RCON_HOST', '192.168.8.218')
os.environ.setdefault('RCON_PORT', '32330')
import rcon as RC

from tputils import PLUGIN_LOG as LOG
OUT = r'C:\Dev\_research\slotD\ab_pairs.json'
WIN = 300
PAIRS = 3


def log_lines():
    try:
        with open(LOG, 'r', encoding='utf-8', errors='replace') as f:
            return f.read().splitlines()
    except Exception:
        return []


def count_windows():
    return sum(1 for l in log_lines() if 'window result:' in l)


def rcon(cmd, timeout=20):
    try:
        return RC.rcon(cmd, timeout=timeout)
    except Exception as e:
        return 'ERR %r' % e


def last_trim_line():
    for l in reversed(log_lines()):
        if 'overlaptrim' in l or 'overlapall' in l:
            return l
    return ''


def hand(name, trim_cmd, settle=25):
    print('\n=== ARM %s (%s) ===' % (name, trim_cmd), flush=True)
    rcon('TickProf.overlapall 0')
    time.sleep(settle)
    rcon(trim_cmd)
    time.sleep(12)
    base = last_trim_line()
    print('   state: %s' % base, flush=True)
    before = count_windows()
    rcon('TickProf.window %d' % WIN)
    t0 = time.time()
    while time.time() - t0 < WIN + 40:
        time.sleep(10)
        if count_windows() > before:
            break
    lines = [l for l in log_lines() if 'window result:' in l]
    rec = {'hand': name, 'trim': trim_cmd, 'state': base}
    if lines:
        last = lines[-1]
        rec['raw'] = last
        m = re.search(r't/s=([\d.]+).*cpu=([\d.]+)s ms/tick=([\d.]+) frame_ms=([\d.]+) busy=([\d.]+)% save=(\w+) (VALID|CONTAMINATED)', last)
        if m:
            rec.update({'tps': float(m.group(1)), 'cpu_s': float(m.group(2)), 'ms_tick': float(m.group(3)),
                        'frame_ms': float(m.group(4)), 'busy': float(m.group(5)), 'save': m.group(6),
                        'valid': m.group(7)})
        print('   %s' % last, flush=True)
    else:
        print('   WINDOW NOT OBTAINED', flush=True)
    return rec


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    pairs = []
    for p in range(1, PAIRS + 1):
        a = hand('A#%d (trim2)' % p, 'TickProf.overlaptrim 2')
        b = hand('B#%d (trim3)' % p, 'TickProf.overlaptrim3')
        pairs.append({'pair': p, 'A': a, 'B': b})
        with open(OUT, 'w', encoding='utf-8') as f:
            json.dump(pairs, f, ensure_ascii=False, indent=2)
        if a.get('valid') and b.get('valid'):
            print('\n--- pair %d: A t/s=%.2f ms/tick=%.1f | B t/s=%.2f ms/tick=%.1f | delta t/s %+.2f, ms/tick %+.2f' %
                  (p, a['tps'], a['ms_tick'], b['tps'], b['ms_tick'], b['tps'] - a['tps'], b['ms_tick'] - a['ms_tick']), flush=True)
        else:
            print('\n--- pair %d: window invalid (A=%s B=%s) - no decision is taken' %
                  (p, a.get('valid'), b.get('valid')), flush=True)
    print('\nSUMMARY:', flush=True)
    for pr in pairs:
        a, b = pr['A'], pr['B']
        if a.get('valid') and b.get('valid'):
            print('  pair %d: d(t/s)=%+.2f  d(ms/tick)=%+.2f  [A %.2f/%.1f, B %.2f/%.1f]' %
                  (pr['pair'], b['tps'] - a['tps'], b['ms_tick'] - a['ms_tick'],
                   a['tps'], a['ms_tick'], b['tps'], b['ms_tick']))
        else:
            print('  pair %d: invalid' % pr['pair'])


if __name__ == '__main__':
    main()

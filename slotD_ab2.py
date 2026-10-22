# -*- coding: utf-8 -*-
# A/B series, round 2: pairs are SYNCHRONIZED with the "clean" interval between
# autosaves (autosave period is exactly 15 min; a 300 s window + ~11.5 min prep
# => both arms of a pair fit between two saves => windows are not contaminated).
#
# Protocol of each arm: overlapall 0 (base reset) -> pause -> its own trim -> pause
# -> 300 s window -> parse the "window result:" line from the log.
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
OUT = r'C:\Dev\_research\slotD\ab_pairs2.json'
WIN = 300
PAIRS = 3


def log_lines():
    try:
        with open(LOG, 'r', encoding='utf-8', errors='replace') as f:
            return f.read().splitlines()
    except Exception:
        return []


def last_save_end():
    for l in reversed(log_lines()):
        if 'save: .ark write finished' in l:
            return l
    return ''


def count_windows():
    return sum(1 for l in log_lines() if 'window result:' in l)


def rcon(cmd, timeout=20):
    try:
        return RC.rcon(cmd, timeout=timeout)
    except Exception as e:
        return 'ERR %r' % e


def wait_next_clean_slot(max_wait=20 * 60):
    """Wait for the nearest save to finish + 20 s so the window does not overlap the world write."""
    seen = last_save_end()
    t0 = time.time()
    while time.time() - t0 < max_wait:
        cur = last_save_end()
        if cur != seen and cur:
            print('   save finished: %s -> starting in 20 s' % cur, flush=True)
            time.sleep(20)
            return True
        time.sleep(10)
    print('   save never seen, starting as is', flush=True)
    return False


def hand(name, trim_cmd, settle=25):
    print('\n=== ARM %s (%s) ===' % (name, trim_cmd), flush=True)
    rcon('TickProf.overlapall 0')
    time.sleep(settle)
    rcon(trim_cmd)
    time.sleep(12)
    state = ''
    for l in reversed(log_lines()):
        if 'overlaptrim' in l:
            state = l
            break
    print('   state: %s' % state, flush=True)
    before = count_windows()
    rcon('TickProf.window %d' % WIN)
    t0 = time.time()
    while time.time() - t0 < WIN + 60:
        time.sleep(10)
        if count_windows() > before:
            break
    lines = [l for l in log_lines() if 'window result:' in l]
    rec = {'hand': name, 'trim': trim_cmd, 'state': state}
    nums = [l for l in lines if 't/s=' in l]
    cont = [l for l in lines if 'contaminated' in l]
    if nums:
        last = nums[-1]
        rec['raw'] = last
        m = re.search(r't/s=([\d.]+).*cpu=([\d.]+)s ms/tick=([\d.]+) frame_ms=([\d.]+) busy=([\d.]+)% save=(\w+) (VALID|CONTAMINATED)', last)
        if m:
            rec.update({'tps': float(m.group(1)), 'cpu_s': float(m.group(2)), 'ms_tick': float(m.group(3)),
                        'frame_ms': float(m.group(4)), 'busy': float(m.group(5)), 'save': m.group(6),
                        'valid': m.group(7)})
        if cont:
            rec['contaminated'] = cont[-1]
        print('   %s' % last, flush=True)
        if cont:
            print('   %s' % cont[-1], flush=True)
    else:
        print('   WINDOW NOT OBTAINED', flush=True)
    return rec


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    pairs = []
    for p in range(1, PAIRS + 1):
        print('\n########## PAIR %d ##########' % p, flush=True)
        wait_next_clean_slot()
        a = hand('A#%d (trim2)' % p, 'TickProf.overlaptrim 2')
        b = hand('B#%d (trim3)' % p, 'TickProf.overlaptrim3')
        pairs.append({'pair': p, 'A': a, 'B': b})
        with open(OUT, 'w', encoding='utf-8') as f:
            json.dump(pairs, f, ensure_ascii=False, indent=2)
        if a.get('valid') and b.get('valid'):
            print('\n--- pair %d ACCEPTED: d(t/s)=%+.2f d(ms/tick)=%+.2f' %
                  (p, b['tps'] - a['tps'], b['ms_tick'] - a['ms_tick']), flush=True)
        else:
            print('\n--- pair %d not accepted (A=%s B=%s)' % (p, a.get('valid'), b.get('valid')), flush=True)
    print('\nROUND 2 SUMMARY:', flush=True)
    for pr in pairs:
        a, b = pr['A'], pr['B']
        ok = a.get('valid') == 'VALID' and b.get('valid') == 'VALID'
        print('  pair %d: %s d(t/s)=%+.2f d(ms/tick)=%+.2f' %
              (pr['pair'], 'ACCEPTED' if ok else 'no',
               b.get('tps', 0) - a.get('tps', 0), b.get('ms_tick', 0) - a.get('ms_tick', 0)), flush=True)


if __name__ == '__main__':
    main()

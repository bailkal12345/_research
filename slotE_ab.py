# -*- coding: utf-8 -*-
# Slot E: A/B series bptrace OFF/ON on real sampling windows.
# Slot D methodology (slotD_ab2.py): TickProf.window 120 -> window line
# (t/s, cpu, ms/tick, VALID/CONTAMINATED); a 65 s pause between windows (cooldown);
# windows start after the nearest save (clean interval of the 15-minute cadence).
# Total: 2 OFF/ON pairs. Then bptrace 0 and a liveness check.
import re
import sys
import time

sys.path.insert(0, r'C:\Dev\_research')
from slotD_ab2 import count_windows, log_lines, rcon, wait_next_clean_slot  # noqa: E402

WIN = 120
from tputils import PLUGIN_LOG as LOG


def last_window_line():
    for l in reversed(log_lines()):
        if 'window result:' in l and 't/s=' in l:
            return l
    return ''


def run_hand(tag, bp_state, win_line_before):
    rcon('TickProf.bptrace %d' % bp_state)
    time.sleep(4)
    rcon('TickProf.window %d' % WIN)
    t0 = time.time()
    while time.time() - t0 < WIN + 90:
        l = last_window_line()
        if l and l != win_line_before:
            time.sleep(2)
            return tag, last_window_line()
        time.sleep(6)
    return tag, 'WINDOW TIMEOUT: ' + last_window_line()


def parse(line):
    m = re.search(r't/s=([\d.]+).*cpu=([\d.]+)s ms/tick=([\d.]+) frame_ms=([\d.]+) '
                  r'busy=([\d.]+)% save=(\w+) (VALID|CONTAMINATED)', line)
    if not m:
        return None
    return {'t/s': float(m.group(1)), 'cpu_s': float(m.group(2)), 'ms/tick': float(m.group(3)),
            'valid': m.group(7)}


print('=== waiting for a clean interval after the save ===', flush=True)
wait_next_clean_slot()

hands = [('OFF-1', 0), ('OFF-2', 0), ('ON-1', 1), ('ON-2', 1 )]
results = []
for tag, st in hands:
    before = last_window_line()
    tag, line = run_hand(tag, st, before)
    p = parse(line)
    results.append((tag, st, line, p))
    print('  %s: %s' % (tag, line[:180]), flush=True)
    if tag not in ('ON-2',):
        time.sleep(65)  # cooldown after the sampler window
rcon('TickProf.bptrace 0')
time.sleep(3)

print('\n=== summary ===', flush=True)
ok = []
for tag, st, line, p in results:
    if not p:
        print('  %s: parse failed' % tag)
        continue
    ok.append((tag, st, p))
out = []
for i, (tag, st, p) in enumerate(ok):
    out.append('%s t/s=%.2f ms/tick=%.2f %s' % (tag, p['t/s'], p['ms/tick'], p['valid']))
print('; '.join(out), flush=True)

pairs = []
arm_off = [p for tag, st, p in ok if st == 0]
arm_on = [p for tag, st, p in ok if st == 1]
if len(arm_off) >= 2 and len(arm_on) >= 2:
    for k in (0, 1):
        a, b = arm_off[k], arm_on[k]
        if a['valid'] == 'VALID' and b['valid'] == 'VALID':
            pairs.append((b['t/s'] - a['t/s'], b['ms/tick'] - a['ms/tick']))
for i, (dt, dm) in enumerate(pairs, 1):
    print('pair %d: d(t/s)=%+.2f d(ms/tick)=%+.2f' % (i, dt, dm), flush=True)

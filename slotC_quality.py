# -*- coding: utf-8 -*-
# Slot C: quality check of windows A/B - were there any "phases" (t/s dips) in the window,
# and how are t/s distributed (median/quartiles/share of low values).
import json, os, sys, statistics
sys.stdout.reconfigure(encoding='utf-8')
OUT = r'C:\Dev\_research\slotC'


def load(tag):
    p = os.path.join(OUT, 'window_%s.json' % tag)
    if not os.path.exists(p):
        return None
    with open(p, 'r', encoding='utf-8') as f:
        return json.load(f)


for tag in ('A_trim2', 'B_trim3', 'C_after_rollback'):
    d = load(tag)
    if not d:
        print('%-16s (none)' % tag)
        continue
    rows = d['rows']
    ts = [r['ts'] for r in rows]
    low = [t for t in ts if t < 45]
    print('%-16s n=%d  mean=%.2f med=%.1f  <45: %d (%.1f%%)  <30: %d  max=%d' % (
        tag, len(ts), statistics.mean(ts), statistics.median(ts),
        len(low), 100.0 * len(low) / len(ts), len([t for t in ts if t < 30]), max(ts)))
    # "phase" = 3+ consecutive t/s<45
    eps, cur = [], []
    for t in ts:
        if t < 45:
            cur.append(t)
        else:
            if len(cur) >= 3:
                eps.append(cur)
            cur = []
    if len(cur) >= 3:
        eps.append(cur)
    print('                 t/s<45 episodes (3+ in a row): %d %s' % (
        len(eps), [len(e) for e in eps][:6]))
    # split the window into 5 equal parts - trend
    n = len(ts)
    if n >= 10:
        parts = [ts[i * n // 5:(i + 1) * n // 5] for i in range(5)]
        print('                 trend over 5 parts of the window: %s' % [
            ' '.join('%.1f' % statistics.mean(p) for p in parts)])

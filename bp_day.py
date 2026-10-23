# -*- coding: utf-8 -*-
# Half-day BlueprintProf production analysis from the downloaded CSV set.
# bp_history<copy>.csv = cumulative snapshots (union of top-N-by-self and candidate rows
# per 10-min interval, same row may repeat across copies - deduped by (proc, ts, function)).
import csv
import glob
import os
import sys
from collections import defaultdict

SRC = r'C:\Users\Admin\Desktop\bp_'
sys.stdout.reconfigure(encoding='utf-8')

rows_all = {}
for p in glob.glob(SRC + r'\bp_history*.csv'):
    tail = os.path.basename(p)[len('bp_history'):].replace('(', '').replace(')', '')
    body = tail.replace('.csv', '').strip()
    try:
        n = int(body) if body else 0
    except ValueError:
        n = 0
    with open(p, encoding='utf-8', errors='replace') as f:
        r = list(csv.reader(f))
    if len(r) >= 2:
        rows_all[n] = r

iv = {}      # (proc, ts) -> context dict
fr = {}      # (proc, ts, function) -> merged row
for n in sorted(rows_all):
    rr = rows_all[n]
    if rr[0][0] != 'proc_id':
        continue
    for row in rr[1:]:
        if len(row) < 19 or not row[4]:
            continue
        key3 = (row[0], row[1], row[9])
        key2 = (row[0], row[1])
        if key2 not in iv:
            iv[key2] = dict(map=row[2], up=float(row[3]), int_s=float(row[4]), tps=float(row[5]),
                            ms_tick=float(row[6]), players=float(row[7]), save=float(row[8]))
        g = fr.get(key3)
        if g is None:
            fr[key3] = dict(calls=int(row[10]), self_ms=float(row[11]), total_ms=float(row[12]),
                            share=float(row[14]), frame=float(row[15]), cand=int(row[16]),
                            repeat=1)
        else:  # same row seen again in a later copy: prefer the later (largest) counts
            if float(row[11]) > g['self_ms']:
                g.update(calls=int(row[10]), self_ms=float(row[11]), total_ms=float(row[12]),
                         share=float(row[14]), frame=float(row[15]), cand=int(row[16]))
            g['repeat'] += 1

# BP total per interval: self_ms gets scaled over all rows; the interval's full BP self
# total = self_ms * 100 / share_pct on the best-precision (max) row we have
per_iv = defaultdict(lambda: dict(frame_sum=0.0, cands=0, n=0, best=None))
for (proc, ts, name), g in fr.items():
    b = per_iv[(proc, ts)]
    b['n'] += 1
    b['frame_sum'] += g['frame']
    if g['cand']:
        b['cands'] += 1
    if g['share'] > b['n'] and True:
        pass
    est = g['self_ms'] * 100.0 / g['share'] if g['share'] > 0 else 0
    if est > (b['best'] or 0):
        b['best'] = est

proc_meta = {}
for proc in sorted(set(k[0] for k in iv)):
    for mp in sorted(set(iv[k]['map'] for k in iv if k[0] == proc)):
        keys = [k for k in iv if k[0] == proc and iv[k]['map'] == mp]
        ctxs = [iv[k] for k in keys]
        frames = [per_iv[k]['frame_sum'] for k in keys]
        frames.sort()
        proc_meta[(proc, mp)] = dict(
            n=len(keys), up=max(c['up'] for c in ctxs),
            tps=sum(c['tps'] for c in ctxs) / len(keys),
            ms=sum(c['ms_tick'] for c in ctxs) / len(keys),
            pl=sum(c['players'] for c in ctxs) / len(keys),
            bp_cpu=sum(frames) / len(frames), bp_p85=frames[min(len(frames) - 1, int(len(frames) * .85))],
            cands=sum(per_iv[k]['cands'] for k in keys) / len(keys))
procs_sorted = sorted(proc_meta)

print('== procs x map (each row = one prod server, started 06:57-06:58) ==')
for key in procs_sorted:
    m = proc_meta[key]
    print('%s map=%-13s iv=%3d up=%5.1fmin tps=%4.1f ms_tick=%5.3f pl=%4.1f  BPcpu mean=%4.1f%% p85=%4.1f%%  cands=%4.1f'
          % (key[0], key[1], m['n'], m['up'], m['tps'], m['ms'], m['pl'],
             m['bp_cpu'], m['bp_p85'], m['cands']))

agg = defaultdict(lambda: [0, 0.0, 0.0, 0.0, set(), 0])
for (proc, ts, name), g in fr.items():
    a = agg[name]
    a[0] += g['calls']
    a[1] += g['self_ms']
    a[2] += g['total_ms']
    a[3] = max(a[3], g['share'])  # keep max interval share per function
    a[4].add(proc)
    a[5] += 1

print('\n== top functions by aggregated self_ms over the fleet (sum of max-cost intervals) ==')
print('%5s %10s %9s %6s  %s' % ('procs', 'self_ms', 'calls', 'maxsh%', 'function'))
for name, a in sorted(agg.items(), key=lambda kv: -kv[1][1])[:16]:
    print('%5d %10.0f %9d %5.1f%%  %s' % (len(a[4]), a[1], a[0], a[3], name.replace('Function /Game/', '')[:120]))

print('\n== per proc/map: mean BP-VM self total (ms per 600 s interval) ==')
for key in procs_sorted:
    m = proc_meta[key]
    tots = [per_iv[k]['best'] for k in iv if (k[0], iv[k]['map']) == key and per_iv[k]['best']]
    if not tots:
        continue
    mean = sum(tots) / len(tots)
    print('%s map=%-13s BP self total = %7.0f ms / 600 s interval (%4.1f%% of interval wall)'
          % (key[0], key[1], mean, mean / 6000.))

chronic = {}
for (proc, ts, name), g in fr.items():
    k = (proc, name)
    c = chronic.setdefault(k, [0, 0])
    c[1] += 1
    if g['cand']:
        c[0] += 1
print('\n== chronic candidates (candidate in ~100% of a proc intervals, >=6 intervals) ==')
ch = [(k, v) for k, v in chronic.items() if v[0] >= 6 and v[0] >= v[1] - 2]
ch.sort(key=lambda kv: -kv[1][0])
for (proc, name), (c, t) in ch[:14]:
    print('%3d/%-3d %s' % (c, t, name.replace('Function /Game/', '')[:110]))

print('\n== mean tps per hour bucket (fleet) ==')
hour = defaultdict(list)
for (proc, ts), c in iv.items():
    hour[ts[11:13]].append(c['tps'])
for h in sorted(hour):
    v = hour[h]
    print('%s:00-59  tps=%.1f (n=%d)' % (h, sum(v) / len(v), len(v)))

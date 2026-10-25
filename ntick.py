# -*- coding: utf-8 -*-
# Native tick from the FLEET csv: ms_tick (whole tick) - BP ms/frame = native ms/tick.
# Per interval: frames = tps * interval_s; bp_ms_frame = sum(self_ms)/frames.
# bp_history*.csv deduped on (proc_id, ts, function) exactly as in bp_fleet.py.
import csv, glob, os, collections, statistics as st

D = r'C:\Users\Admin\Desktop\csv'

seen = set()
iv = collections.OrderedDict()
for path in sorted(glob.glob(os.path.join(D, 'bp_history*.csv'))):
    for x in csv.DictReader(open(path, encoding='utf-8-sig')):
        k = (x['proc_id'], x['ts'], x['function'])
        if k in seen:
            continue
        seen.add(k)
        ik = (x['proc_id'], x['map'], x['ts'])
        d = iv.setdefault(ik, dict(tps=float(x['tps']), ms_tick=float(x['ms_tick']),
                                   iv_s=float(x['interval_s']), players=float(x['players']),
                                   save_s=float(x['ark_save_s']), bp=0.0, bpf=0))
        d['bp'] += float(x['self_ms'])
        d['bpf'] += 1

rows = []
for (proc, m, ts), d in iv.items():
    frames = d['tps'] * d['iv_s']
    if frames <= 0 or d['ms_tick'] <= 0:
        continue
    bp_f = d['bp'] / frames
    nat = d['ms_tick'] - bp_f
    rows.append(dict(map=m, proc=proc, ts=ts, tps=d['tps'], ms_tick=d['ms_tick'],
                     bp=bp_f, nat=nat, players=d['players'],
                     save_ms_f=d['save_s'] * 1000.0 / frames,
                     bp_share=100.0 * bp_f / d['ms_tick'], nfunc=d['bpf']))

print('intervals %d, maps %d' % (len(rows), len(set(r['map'] for r in rows))))
print()
hdr = ('%-16s %4s %6s %7s %7s %7s %7s %7s %6s' %
       ('map', 'iv', 'tps', 'ms_tick', 'bp_ms', 'nat_ms', 'bp%', 'save_ms', 'plr'))
print(hdr)
bymap = collections.defaultdict(list)
for r in rows:
    bymap[r['map']].append(r)
tot = dict(nat=[], bp=[], bp_share=[])
for m in sorted(bymap, key=lambda z: -st.median([r['nat'] for r in bymap[z]])):
    a = bymap[m]
    med = lambda f: st.median([r[f] for r in a])
    print('%-16s %4d %6.2f %7.2f %7.3f %7.2f %6.1f%% %7.2f %6.1f' % (
        m, len(a), med('tps'), med('ms_tick'), med('bp'), med('nat'),
        med('bp_share'), med('save_ms_f'), med('players')))
    tot['nat'] += [r['nat'] for r in a]
    tot['bp'] += [r['bp'] for r in a]
    tot['bp_share'] += [r['bp_share'] for r in a]

print()
print('FLEET: ms_tick median %.2f | bp ms/frame median %.3f | native median %.2f | bp share median %.1f%%'
      % (st.median([r['ms_tick'] for r in rows]), st.median([r['bp'] for r in rows]),
         st.median([r['nat'] for r in rows]), st.median([r['bp_share'] for r in rows])))
print('native p10/p25/p75/p90: %.2f / %.2f / %.2f / %.2f'
      % tuple(st.quantiles([r['nat'] for r in rows], n=10)[i] for i in (1, 4, 6, 8)))
print()
print('== native vs players (fleet, correlation) ==')
xs = [r['players'] for r in rows]
ys = [r['nat'] for r in rows]
n = len(xs)
mx, my = sum(xs) / n, sum(ys) / n
cov = sum((a - mx) * (b - my) for a, b in zip(xs, ys)) / n
sx = (sum((a - mx) ** 2 for a in xs) / n) ** .5
sy = (sum((b - my) ** 2 for b in ys) / n) ** .5
print('pearson r(native, players) = %.3f' % (cov / (sx * sy)))
print()
print('== native vs save load ==')
for lo, hi in ((0, 0.01), (0.01, 0.2), (0.2, 1.0), (1.0, 99)):
    g = [r for r in rows if lo <= r['save_ms_f'] < hi]
    if g:
        print('save_ms/frame [%5.2f,%5.2f): n=%4d native median %.2f ms/tick, ms_tick %.2f'
              % (lo, hi, len(g), st.median([r['nat'] for r in g]),
                 st.median([r['ms_tick'] for r in g])))
print()
print('== Genesis-family check: native per 100 players ==')
for m in sorted(bymap):
    a = bymap[m]
    print('%-16s players med %5.1f  native med %6.2f  bp med %5.2f' % (
        m, st.median([r['players'] for r in a]), st.median([r['nat'] for r in a]),
        st.median([r['bp'] for r in a])))

import csv, glob, os, collections, json

D = r'C:\Users\Admin\Desktop\csv'

def load_all():
    rows = []
    seen = set()
    for path in glob.glob(os.path.join(D, 'bp_history*.csv')):
        for x in csv.DictReader(open(path, encoding='utf-8-sig')):
            k = (x['proc_id'], x['ts'], x['function'])
            if k in seen:
                continue
            seen.add(k)
            x['_file'] = os.path.basename(path)
            rows.append(x)
    return rows

def short(fn):
    f = fn.replace('Function ', '')
    if '.' in f:
        f = f.split('.')[-1]
    return f

rows = load_all()
print('total rows', len(rows))

iv = collections.OrderedDict()
for x in rows:
    k = (x['proc_id'], x['map'], x['ts'])
    d = iv.setdefault(k, dict(tps=float(x['tps']), ms_tick=float(x['ms_tick']),
                              players=int(float(x['players'])), uptime=float(x['uptime_min']),
                              save=float(x['ark_save_s']), self_ms=0.0, funcs=0))
    d['self_ms'] += float(x['self_ms'])
    d['funcs'] += 1

print('intervals', len(iv), 'maps', len(set(k[1] for k in iv)))

# per-map table
bymap = collections.defaultdict(list)
for k, v in iv.items():
    bymap[k[1]].append(v)

print()
print('%-16s %4s %6s %7s %7s %9s %7s %7s %7s' % ('map', 'iv', 'tps', 'ms_tick', 'plr', 'bp_self_s', 'bp_ms/f', 'bp%cpu', 'save_s'))
fleet_self = fleet_frame = 0.0
for m in sorted(bymap, key=lambda z: -sum(v['self_ms'] for v in bymap[z])):
    a = bymap[m]
    n = len(a)
    tps = sum(v['tps'] for v in a) / n
    mt = sum(v['ms_tick'] for v in a) / n
    plr = sum(v['players'] for v in a) / n
    self_s = sum(v['self_ms'] for v in a) / 1000
    per_iv = self_s / n
    frames = sum(600.0 * v['tps'] for v in a)
    per_frame_ms = self_s * 1000 / frames
    cpu = 100 * self_s / (n * 600.0 * tps * (mt / 1000.0)) if tps else 0
    save = sum(v['save'] for v in a) / n
    fleet_self += self_s
    fleet_frame += frames
    print('%-16s %4d %6.2f %7.2f %7.1f %9.1f %7.3f %6.1f%% %7.2f' % (
        m, n, tps, mt, plr, self_s, per_frame_ms, cpu, save))

print()
print('fleet: BP self %.1f s over %.0f s wall = %.3f%% of wall' % (
    fleet_self, fleet_frame, 100 * fleet_self / fleet_frame))

# per-map top5
print()
for m in sorted(bymap):
    g = collections.defaultdict(float)
    c = collections.defaultdict(int)
    for x in rows:
        if x['map'] != m:
            continue
        g[x['function']] += float(x['self_ms'])
        c[x['function']] += int(x['calls'])
    t = sum(g.values())
    top = sorted(g.items(), key=lambda i: -i[1])[:5]
    print('== %s (bp self %.1f s)' % (m, t / 1000))
    for fn, v in top:
        print('   %7.1fs %5.1f%% %9d  %s' % (v / 1000, 100 * v / t, c[fn], short(fn)[:70]))

# mod share
mod = collections.defaultdict(float)
van = 0.0
for x in rows:
    s = float(x['self_ms'])
    if '/Game/Mods/' in x['function']:
        mod[x['map']] += s
    else:
        van += s
tot = van + sum(mod.values())
print()
print('mod share %.1f%% vanilla %.1f%%' % (100 * sum(mod.values()) / tot, 100 * van / tot))
print('mod by map:', {k: round(v / 1000, 1) for k, v in sorted(mod.items(), key=lambda i: -i[1])})

# function family
fam = collections.defaultdict(lambda: [0.0, 0])
for x in rows:
    s = short(x['function'])
    fn = s.split(':')[-1] if ':' in s else s
    fam[fn][0] += float(x['self_ms'])
    fam[fn][1] += int(x['calls'])
print()
print('== function families ==')
for k, v in sorted(fam.items(), key=lambda i: -i[1][0])[:15]:
    print('%8.1fs %5.1f%% %10d  %s' % (v[0] / 1000, 100 * v[0] / tot, v[1], k))

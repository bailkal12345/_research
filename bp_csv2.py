import csv, os, collections

D = r'C:\Users\Admin\Desktop\csv'
rows = list(csv.DictReader(open(os.path.join(D, 'bp_history.csv'), encoding='utf-8-sig')))

iv = {}
for x in rows:
    iv.setdefault((x['proc_id'], x['ts']), dict(tps=float(x['tps']), players=int(float(x['players'])), upt=float(x['uptime_min'])))

recs = []
for x in rows:
    k = (x['proc_id'], x['ts'])
    recs.append((iv[k]['tps'], iv[k]['players'], x['function'], float(x['self_ms']), int(x['calls'])))


def top(sel, n=12):
    g = collections.defaultdict(float)
    c = collections.defaultdict(int)
    for a in sel:
        g[a[2]] += a[3]
        c[a[2]] += a[4]
    t = sum(g.values())
    out = []
    for k, v in sorted(g.items(), key=lambda i: -i[1])[:n]:
        out.append((round(v / 1000, 1), round(100 * v / t, 1), c[k], k.split('.')[-1][:60]))
    return t, out


for name, lo, hi in [('low tps <11', 0, 11), ('mid 11-12', 11, 12), ('hi >=12', 12, 100)]:
    sel = [a for a in recs if lo <= a[0] < hi]
    t, out = top(sel)
    ivs = len(set((a[0], a[1]) for a in sel))
    print('=== %s | rows=%d bp_self=%.1fs' % (name, len(sel), t / 1000))
    for o in out:
        print('   %8.1f %5.1f%% %9d  %s' % o)
    print()

# per-interval BP self normalized
print('=== per-interval BP self time vs tps')
ivagg = collections.defaultdict(float)
for x in rows:
    ivagg[(x['proc_id'], x['ts'])] += float(x['self_ms'])
buckets = collections.defaultdict(list)
for k, v in ivagg.items():
    t = iv[k]['tps']
    b = 'tps<5' if t < 5 else ('tps5-11' if t < 11 else ('tps11-13' if t < 13 else 'tps>13'))
    buckets[b].append((v, iv[k]['players'], len(k)))
for b in ['tps<5', 'tps5-11', 'tps11-13', 'tps>13']:
    a = buckets[b]
    if not a:
        continue
    print('%-9s n=%3d avg_bp_self=%.2fs  med=%.2fs' % (b, len(a), sum(x[0] for x in a) / len(a) / 1000, sorted(x[0] for x in a)[len(a) // 2] / 1000))

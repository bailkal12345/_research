import csv, os, collections

D = r'C:\Users\Admin\Desktop\csv'


def load(name):
    return list(csv.DictReader(open(os.path.join(D, name), encoding='utf-8-sig')))


def short(fn):
    f = fn.replace('Function ', '')
    if '.' in f:
        f = f.split('.')[-1]
    return f


def agg(rows, key='function'):
    a = collections.defaultdict(lambda: [0.0, 0, 0.0])
    for x in rows:
        k = x[key]
        a[k][0] += float(x['self_ms'])
        a[k][1] += int(x['calls'])
        a[k][2] += float(x['total_ms'])
    return a


def intervals(rows):
    iv = collections.OrderedDict()
    for x in rows:
        k = (x['proc_id'], x['ts'])
        if k not in iv:
            iv[k] = dict(map=x['map'], tps=float(x['tps']), ms_tick=float(x['ms_tick']),
                         players=int(float(x['players'])), uptime=float(x['uptime_min']),
                         save=float(x['ark_save_s']), self_ms=0.0, funcs=0)
        iv[k]['self_ms'] += float(x['self_ms'])
        iv[k]['funcs'] += 1
    return iv


def main():
    rows = load('bp_history.csv')
    print('rows', len(rows), 'funcs', len(set(x['function'] for x in rows)))
    iv = intervals(rows)
    print('intervals', len(iv))
    print('procs', collections.Counter(x['proc_id'] for x in rows))
    print()

    # per-interval BP self time as fraction of wall frame budget
    print('%-18s %-6s %5s %7s %7s %8s %7s' % ('ts', 'proc', 'plr', 'tps', 'ms_tick', 'bp_self_s', 'bp/frame%'))
    for k, v in sorted(iv.items(), key=lambda i: i[0][1])[:12]:
        frames = 600.0 * v['tps']
        print('%-18s %-6s %5d %7.2f %7.2f %8.2f %7.1f' % (
            k[1], k[0][-6:], v['players'], v['tps'], v['ms_tick'], v['self_ms'] / 1000,
            100 * (v['self_ms'] / 1000) / frames))
    print()

    # total BP self vs total frame time
    frames_all = sum(600.0 * v['tps'] for v in iv.values())
    bp_all = sum(v['self_ms'] for v in iv.values()) / 1000
    print('overall: BP self %.1f s over %.1f s of frame time = %.1f%%' % (bp_all, frames_all, 100 * bp_all / frames_all))
    print()

    # --- top functions with per-call cost in us, self share, and concurrency proxy
    a = agg(rows)
    tot = sum(v[0] for v in a.values())
    print('%-9s %6s %10s %8s %9s  %s' % ('self_s', 'pct', 'calls', 'us/call', 'per_intv', 'function'))
    for k, v in sorted(a.items(), key=lambda i: -i[1][0])[:45]:
        per_intv = v[1] / max(len(iv), 1)
        print('%-9.2f %5.2f%% %10d %8.2f %9.0f  %s' % (
            v[0] / 1000, 100 * v[0] / tot, v[1], v[0] / max(v[1], 1) * 1000, per_intv, short(k)))
    print()

    # --- categories by class
    cat = collections.defaultdict(float)
    for k, v in a.items():
        s = short(k)
        cls = s.split(':')[0]
        cat[cls] += v[0]
    print('== top 25 classes by self ==')
    for k, v in sorted(cat.items(), key=lambda i: -i[1])[:25]:
        print('%-9.2f %5.2f%%  %s' % (v / 1000, 100 * v / tot, k))
    print()

    # --- function name suffix categories
    suf = collections.defaultdict(lambda: [0.0, 0])
    for k, v in a.items():
        s = short(k)
        fn = s.split(':')[-1] if ':' in s else s
        suf[fn][0] += v[0]
        suf[fn][1] += v[1]
    print('== top 20 function names by self ==')
    for k, v in sorted(suf.items(), key=lambda i: -i[1][0])[:20]:
        print('%-9.2f %5.2f%% %10d  %s' % (v[0] / 1000, 100 * v[0] / tot, v[1], k))


if __name__ == '__main__':
    main()

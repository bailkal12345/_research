# -*- coding: utf-8 -*-
# Slot C: PHASE-AWARE comparison of windows A/B.
#
# Both windows contain a cumulative phase (t/s<45) in the last quarter - therefore a naive
# window average mixes two different regimes. Instead we compare FLAT segments pairwise
# (index in window A against the same index in window B): fair, since both windows
# start at the same point of the save cycle.
import json, os, sys, statistics
sys.stdout.reconfigure(encoding='utf-8')
OUT = r'C:\Dev\_research\slotC'


def load(tag):
    p = os.path.join(OUT, 'window_%s.json' % tag)
    if not os.path.exists(p):
        return None
    with open(p, 'r', encoding='utf-8') as f:
        return json.load(f)


A, B = load('A_trim2'), load('B_trim3')
if not (A and B):
    print('both windows missing')
    sys.exit(0)

a = [r['ts'] for r in A['rows']]
b = [r['ts'] for r in B['rows']]
n = min(len(a), len(b))
a, b = a[:n], b[:n]

# 1) split by regime MATCHING (both windows: t/s<45 or not)
pairs = list(zip(a, b))
phase = [(x, y) for x, y in pairs if x < 45 and y < 45]
clean = [(x, y) for x, y in pairs if x >= 45 and y >= 45]
mixed = [(x, y) for x, y in pairs if (x < 45) != (y < 45)]

print('=== pairwise comparison (n=%d) ===' % n)
print('  regimes matched: "clean" (t/s>=45) %d, "phase" (<45) %d, different %d' % (
    len(clean), len(phase), len(mixed)))


def st(v):
    return 'mean=%.2f med=%.1f min=%d' % (statistics.mean(v), statistics.median(v), min(v)) if v else 'n/a'


if clean:
    ax = [x for x, _ in clean]
    bx = [y for _, y in clean]
    print('  CLEAN SEGMENT (both windows t/s>=45):')
    print('     A(trim2): %s' % st(ax))
    print('     B(trim3): %s' % st(bx))
    print('     delta B-A: %+.2f t/s' % (statistics.mean(bx) - statistics.mean(ax)))
if phase:
    ax = [x for x, y in phase]
    bx = [y for _, y in phase]
    print('  PHASE (both windows t/s<45):')
    print('     A(trim2): %s' % st(ax))
    print('     B(trim3): %s' % st(bx))
    print('     delta B-A: %+.2f t/s' % (statistics.mean(bx) - statistics.mean(ax)))
if mixed:
    ax = [x for x, y in mixed]
    bx = [y for _, y in mixed]
    print('  DIFFERENT REGIMES (%d points): A=%s B=%s' % (len(mixed), st(ax), st(bx)))

# 2) ms/tick and busy for the same regimes
for key, label in (('ms', 'ms/tick'), ('busy', 'busy%')):
    av = [r[key] for r in A['rows'] if r[key] is not None]
    bv = [r[key] for r in B['rows'] if r[key] is not None]
    m = min(len(av), len(bv))
    av, bv = av[:m], bv[:m]
    print('  %s: A=%.2f  B=%.2f  delta %+.2f' % (label, statistics.mean(av), statistics.mean(bv),
                                                   statistics.mean(bv) - statistics.mean(av)))

# 3) trend over 10 equal parts of the window
print('\n=== trend over 10 equal parts of the window ===')
for nm, v in (('A(trim2)', a), ('B(trim3)', b)):
    parts = [statistics.mean(v[i * n // 10:(i + 1) * n // 10]) for i in range(10)]
    print('  %-9s %s' % (nm, ' '.join('%.0f' % p for p in parts)))

C = load('C_after_rollback')
if C:
    cv = [r['ts'] for r in C['rows']]
    print('\n=== control window after rollback ===')
    print('  n=%d mean=%.2f med=%.1f min=%d max=%d' % (
        len(cv), statistics.mean(cv), statistics.median(cv), min(cv), max(cv)))
    parts = [statistics.mean(cv[i * len(cv) // 10:(i + 1) * len(cv) // 10]) for i in range(10)]
    print('  trend: %s' % ' '.join('%.0f' % p for p in parts))
    res = dict(
        A=dict(ts_mean=statistics.mean(a), ts_med=statistics.median(a)),
        B=dict(ts_mean=statistics.mean(b), ts_med=statistics.median(b)),
        C=dict(ts_mean=statistics.mean(cv), ts_med=statistics.median(cv)) if cv else None,
        delta_BA_all=statistics.mean(b) - statistics.mean(a),
        delta_BA_clean=(statistics.mean([y for _, y in clean]) - statistics.mean([x for x, _ in clean]))
        if clean else None,
        delta_BA_phase=(statistics.mean([y for _, y in phase]) - statistics.mean([x for x, _ in phase]))
        if phase else None)
    with open(os.path.join(OUT, 'phase_aware_compare.json'), 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print('\n' + json.dumps(res, ensure_ascii=False, indent=1))

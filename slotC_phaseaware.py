# -*- coding: utf-8 -*-
# Слот C: ФАЗО-СОПОСТАВИМЫЙ разбор окон A/B.
#
# Оба окна содержат накопительную фазу (t/s<45) в последней четверти - значит
# наивное среднее по окну смешивает два разных режима. Поэтому сравниваем
# ПОМИнутные участки, попарно (индекс в окне A против того же индекса в окне B):
# это справедливо, т.к. оба окна начинаются в один и тот же момент цикла сейва.
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
    print('нет обоих окон')
    sys.exit(0)

a = [r['ts'] for r in A['rows']]
b = [r['ts'] for r in B['rows']]
n = min(len(a), len(b))
a, b = a[:n], b[:n]

# 1) разбиение на режимы по СОВПАСТАНИЮ режима (оба окна: t/s<45 или нет)
pairs = list(zip(a, b))
phase = [(x, y) for x, y in pairs if x < 45 and y < 45]
clean = [(x, y) for x, y in pairs if x >= 45 and y >= 45]
mixed = [(x, y) for x, y in pairs if (x < 45) != (y < 45)]

print('=== попарное сравнение (n=%d) ===' % n)
print('  режимы совпали: "чисто"(t/s>=45) %d, "фаза"(<45) %d, разные %d' % (
    len(clean), len(phase), len(mixed)))


def st(v):
    return 'mean=%.2f med=%.1f min=%d' % (statistics.mean(v), statistics.median(v), min(v)) if v else 'n/a'


if clean:
    ax = [x for x, _ in clean]
    bx = [y for _, y in clean]
    print('  ЧИСТЫЙ УЧАСТОК (оба окна t/s>=45):')
    print('     A(trim2): %s' % st(ax))
    print('     B(trim3): %s' % st(bx))
    print('     дельта B-A: %+.2f t/s' % (statistics.mean(bx) - statistics.mean(ax)))
if phase:
    ax = [x for x, y in phase]
    bx = [y for _, y in phase]
    print('  ФАЗА (оба окна t/s<45):')
    print('     A(trim2): %s' % st(ax))
    print('     B(trim3): %s' % st(bx))
    print('     дельта B-A: %+.2f t/s' % (statistics.mean(bx) - statistics.mean(ax)))
if mixed:
    ax = [x for x, y in mixed]
    bx = [y for _, y in mixed]
    print('  РАЗНЫЕ РЕЖИМЫ (%d точек): A=%s B=%s' % (len(mixed), st(ax), st(bx)))

# 2) мс/тик и busy по тем же режимам
for key, label in (('ms', 'мс/тик'), ('busy', 'busy%')):
    av = [r[key] for r in A['rows'] if r[key] is not None]
    bv = [r[key] for r in B['rows'] if r[key] is not None]
    m = min(len(av), len(bv))
    av, bv = av[:m], bv[:m]
    print('  %s: A=%.2f  B=%.2f  дельта %+.2f' % (label, statistics.mean(av), statistics.mean(bv),
                                                   statistics.mean(bv) - statistics.mean(av)))

# 3) тренд по 10 частям окна (обе руки)
print('\n=== тренд по 10 равным частям окна ===')
for nm, v in (('A(trim2)', a), ('B(trim3)', b)):
    parts = [statistics.mean(v[i * n // 10:(i + 1) * n // 10]) for i in range(10)]
    print('  %-9s %s' % (nm, ' '.join('%.0f' % p for p in parts)))

C = load('C_after_rollback')
if C:
    cv = [r['ts'] for r in C['rows']]
    print('\n=== контрольное окно после отката ===')
    print('  n=%d mean=%.2f med=%.1f min=%d max=%d' % (
        len(cv), statistics.mean(cv), statistics.median(cv), min(cv), max(cv)))
    parts = [statistics.mean(cv[i * len(cv) // 10:(i + 1) * len(cv) // 10]) for i in range(10)]
    print('  тренд: %s' % ' '.join('%.0f' % p for p in parts))
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

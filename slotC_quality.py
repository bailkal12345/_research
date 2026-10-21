# -*- coding: utf-8 -*-
# Слот C: проверка качества окон A/B - были ли в окне "фазы" (t/s провалы),
# и как распределены t/s (медиана/квартили/доля низких значений).
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
        print('%-16s (нет)' % tag)
        continue
    rows = d['rows']
    ts = [r['ts'] for r in rows]
    low = [t for t in ts if t < 45]
    print('%-16s n=%d  mean=%.2f med=%.1f  <45: %d (%.1f%%)  <30: %d  max=%d' % (
        tag, len(ts), statistics.mean(ts), statistics.median(ts),
        len(low), 100.0 * len(low) / len(ts), len([t for t in ts if t < 30]), max(ts)))
    # "фаза" = 3+ подряд t/s<45
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
    print('                 эпизодов t/s<45 (3+ подряд): %d %s' % (
        len(eps), [len(e) for e in eps][:6]))
    # разбиение окна на 5 равных частей - тренд
    n = len(ts)
    if n >= 10:
        parts = [ts[i * n // 5:(i + 1) * n // 5] for i in range(5)]
        print('                 тренд по 5 частям окна: %s' % [
            ' '.join('%.1f' % statistics.mean(p) for p in parts)])

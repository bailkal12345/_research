# -*- coding: utf-8 -*-
# Разбор окон слота C: сравнение A (overlaptrim 2) и B (overlaptrim3) + контрольное
# окно после отката. Печатает таблицу и вердикт.
import json, os, sys, statistics
sys.stdout.reconfigure(encoding='utf-8')
OUT = r'C:\Dev\_research\slotC'


def load(tag):
    p = os.path.join(OUT, 'window_%s.json' % tag)
    if not os.path.exists(p):
        return None
    with open(p, 'r', encoding='utf-8') as f:
        return json.load(f)


def stat(d):
    if not d:
        return None
    rows = d['rows']
    ts = [r['ts'] for r in rows]
    ms = [r['ms'] for r in rows if r['ms']]
    busy = [r['busy'] for r in rows if r['busy'] is not None]
    save = [r['save'] for r in rows if r['save']]
    contam = sum(1 for s in save if s != 'idle')
    return dict(n=len(rows), ts_mean=round(statistics.mean(ts), 2) if ts else None,
                ts_med=statistics.median(ts) if ts else None,
                ts_min=min(ts) if ts else None, ts_max=max(ts) if ts else None,
                ts_p10=sorted(ts)[int(len(ts) * 0.1)] if ts else None,
                ts_p90=sorted(ts)[int(len(ts) * 0.9)] if ts else None,
                ms_mean=round(statistics.mean(ms), 2) if ms else None,
                ms_med=statistics.median(ms) if ms else None,
                busy_mean=round(statistics.mean(busy), 1) if busy else None,
                save_nonidle=contam,
                verdict='CONTAMINATED' if contam else 'VALID')


if __name__ == '__main__':
    tags = ['A_trim2', 'B_trim3', 'C_after_rollback']
    res = {}
    print('%-18s %6s %8s %8s %8s %8s %8s %8s %6s  %s' % (
        'окно', 'строк', 't/s mean', 't/s med', 't/s p10', 't/s p90', 'мс/тик', 'busy%', 'сейв', 'вердикт'))
    for t in tags:
        d = load(t)
        if not d:
            print('%-18s  (нет файла)' % t)
            continue
        s = stat(d)
        res[t] = s
        print('%-18s %6d %8s %8s %8s %8s %8s %8s %6d  %s' % (
            t, s['n'], s['ts_mean'], s['ts_med'], s['ts_p10'], s['ts_p90'],
            s['ms_mean'], s['busy_mean'], s['save_nonidle'], s['verdict']))
    print()
    A, B, C = res.get('A_trim2'), res.get('B_trim3'), res.get('C_after_rollback')
    if A and B:
        print('ДЕЛЬТА B-A: t/s mean %+0.2f (медиана %+0.2f), мс/тик %+0.2f' % (
            B['ts_mean'] - A['ts_mean'], B['ts_med'] - A['ts_med'], B['ms_mean'] - A['ms_mean']))
        if A['verdict'] == 'VALID' and B['verdict'] == 'VALID':
            ok = (B['ts_mean'] >= A['ts_mean'] - 0.5) and (B['ms_mean'] <= A['ms_mean'] + 1.0)
            print('ВЕРДИКТ A/B: %s' % ('trim3 не хуже trim2' if ok else 'trim3 ХУЖЕ trim2 -> в прод не выкатывать'))
        else:
            print('ВЕРДИКТ A/B: окна неполны или контаминированы - решение не принимается')
    if C:
        print('Контрольное окно после отката: t/s mean %s, мс/тик %s, вердикт %s' % (
            C['ts_mean'], C['ms_mean'], C['verdict']))
    with open(os.path.join(OUT, 'compare.json'), 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=1)

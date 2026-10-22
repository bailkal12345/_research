# -*- coding: utf-8 -*-
# Phases over the t/s series (plugin tick counter): a phase = 3+ consecutive lines with t/s<45.
# Classification: high busy% (CPU) or low (blocking). Correlation with save markers.
import re

LOG = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi\Plugins\TickProf\TickProf.log'

re_mon = re.compile(r'^(\d\d:\d\d:\d\d)\.\d+ mon: t/s=(\d+)(?: +ms/tick=(\d+) +frame_ms=(\d+) +busy=(\d+)% +save=(\w+))?')
re_boot = re.compile(r'^(\d\d:\d\d:\d\d)\.\d+ loaded \(Plugin_Init\)')
re_save_start = re.compile(r'^(\d\d:\d\d:\d\d)\.\d+ save: .ark write started')
re_save_end = re.compile(r'^(\d\d:\d\d:\d\d)\.\d+ save: \.ark write finished, duration (\d+) ms')


def hms(t):
    hh, mm, ss = map(int, t.split(':'))
    return hh * 3600 + mm * 60 + ss


def s_hms(s):
    return '%02d:%02d:%02d' % ((s // 3600) % 24, (s % 3600) // 60, s % 60)


def main():
    ev = []
    day = 0
    prev = None
    with open(LOG, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.rstrip('\n')
            if not re.match(r'^\d\d:\d\d:\d\d', line):
                continue
            t = hms(line[:8])
            if prev is not None and t + 24 * 3600 < prev - 6 * 3600:
                day += 24 * 3600
            t += day
            prev = t
            if re_boot.match(line):
                ev.append((t, 'boot', None))
            else:
                m = re_mon.match(line)
                if m:
                    ts = int(m.group(2))
                    msk = int(m.group(3)) if m.group(3) else None
                    fr = int(m.group(4)) if m.group(4) else None
                    busy = int(m.group(5)) if m.group(5) else None
                    sv = m.group(6) if m.group(6) else None
                    ev.append((t, 'mon', (ts, msk, fr, busy, sv)))
                else:
                    m = re_save_start.match(line)
                    if m:
                        ev.append((t, 'save_start', None))
                    else:
                        m = re_save_end.match(line)
                        if m:
                            ev.append((t, 'save_end', int(m.group(2))))

    idx = [i for i, e in enumerate(ev) if e[1] == 'boot']
    print('boots: %d' % len(idx))
    out = []
    total_ph = 0
    for si, s in enumerate(idx):
        end = idx[si + 1] if si + 1 < len(idx) else len(ev)
        chunk = ev[s:end]
        mons = [(e[0], e[2]) for e in chunk if e[1] == 'mon' and e[2]]
        ss = [e[0] for e in chunk if e[1] == 'save_start']
        se = [e[0] for e in chunk if e[1] == 'save_end']
        if len(mons) < 30:
            continue
        t0 = mons[0][0]
        span_min = (mons[-1][0] - t0) / 60.0
        phases = []
        cur = None
        for (t, v) in mons:
            if v[0] < 45:
                if cur is None:
                    cur = {'start': t, 'rows': []}
                cur['rows'].append(v)
            else:
                if cur is not None and len(cur['rows']) >= 3:
                    phases.append(cur)
                cur = None
        if cur is not None and len(cur['rows']) >= 3:
            phases.append(cur)
        total_ph += len(phases)
        out.append('boot#%d @%s (%.0f min, mon=%d): save_start=%d save_end=%d phases=%d' % (
            si, s_hms(t0), span_min, len(mons), len(ss), len(se), len(phases)))
        for ph in phases:
            rows = ph['rows']
            after = [t for (t, v) in mons if t > ph['start'] and v[0] >= 45]
            recov = after[0] if after else None
            dur = (recov - ph['start']) if recov else 0
            ts_min = min(r[0] for r in rows)
            busy_avg = sum((r[3] if r[3] is not None else 0) for r in rows) / len(rows)
            fr_max = max((r[2] if r[2] is not None else 0) for r in rows)
            fr_avg = sum((r[2] if r[2] is not None else 0) for r in rows) / len(rows)
            n_sav = sum(1 for r in rows if r[4] and r[4] != 'idle')
            lss = max((t for t in ss if t <= ph['start']), default=None)
            lse = max((t for t in se if t <= ph['start']), default=None)
            sav_win = any(ph['start'] <= t <= ((recov or ph['start']) + 1) for t in ss)
            mark = []
            if lse is not None and 0 <= ph['start'] - lse <= 90:
                mark.append('save_end within %ds' % (ph['start'] - lse))
            if lss is not None and 0 <= ph['start'] - lss <= 90:
                mark.append('save_start within %ds' % (ph['start'] - lss))
            if sav_win:
                mark.append('save INSIDE the phase')
            if n_sav:
                mark.append('save field != idle: %d rows' % n_sav)
            typ = 'CPU(high busy)' if busy_avg >= 80 else ('BLOCKED(low busy)' if busy_avg < 60 else 'mixed')
            out.append('   PHASE %s..%s dur=%3.1fmin ts_min=%d busy%.0f%% frame_max=%d avg=%dms | %s' % (
                s_hms(ph['start']), s_hms(recov) if recov else '?',
                dur / 60.0, ts_min, busy_avg, fr_max, fr_avg,
                ('; '.join(mark) if mark else 'no save link')))
            out.append('        type=%s' % typ)
    print('\n'.join(out))
    print('total phases:', total_ph)


if __name__ == '__main__':
    main()

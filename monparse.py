# -*- coding: utf-8 -*-
# Phases over the t/s series (plugin tick counter): a phase = 3+ consecutive lines with t/s<45.
# Classification: high busy% (CPU) or low (blocking). Correlation with save markers.
import sys

sys.path.insert(0, r'C:\Dev\_research')
from tputils import log_lines, s_hms
from tputils import RE_MON, RE_BOOT, RE_SAVE_START, RE_SAVE_END


def main():
    ev = []
    for t, line in log_lines():
        if RE_BOOT.match(line):
            ev.append((t, 'boot', None))
        else:
            m = RE_MON.match(line)
            if m:
                ts = int(m.group(2))
                msk = int(m.group(3)) if m.group(3) else None
                fr = int(m.group(4)) if m.group(4) else None
                busy = int(m.group(5)) if m.group(5) else None
                sv = m.group(6) if m.group(6) else None
                ev.append((t, 'mon', (ts, msk, fr, busy, sv)))
            else:
                m = RE_SAVE_START.match(line)
                if m:
                    ev.append((t, 'save_start', None))
                else:
                    m = RE_SAVE_END.match(line)
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

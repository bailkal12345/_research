# -*- coding: utf-8 -*-
# Slot B (doit6 §2): auto-monitoring at 1 Hz + a 60 s profile INSIDE the plateau of the cumulative phase.
#
# Phase criterion: t/s<45 in 3+ consecutive mon lines (as in the previous slot).
# At phase start: TickProf.ticklist (before) -> TickProf.start 60 (profile) ->
# wait for the window to end -> TickProf.ticklist (after).
# Everything is written to C:/Dev/_research/slotB/.
import os, re, sys, time, json, subprocess
sys.path.insert(0, r'C:\Dev\_research')
os.environ.setdefault('RCON_HOST', '192.168.8.218')
os.environ.setdefault('RCON_PORT', '32330')
import rcon as RC

PLUG = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi\Plugins\TickProf'
LOG = os.path.join(PLUG, 'TickProf.log')
OUT = r'C:\Dev\_research\slotB'
os.makedirs(OUT, exist_ok=True)
REP = os.path.join(OUT, 'slotB_log.txt')
re_mon = re.compile(r'mon: t/s=(\d+)(?: ms/tick=(\d+) frame_ms=(\d+) busy=(\d+)% save=(\w+))?')
re_prof = re.compile(r'sampler started, tid=(\d+)')


def say(msg):
    line = '%s %s' % (time.strftime('%H:%M:%S'), msg)
    print(line, flush=True)
    with open(REP, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def rcon(cmd, timeout=15):
    try:
        return RC.rcon(cmd, timeout=timeout)
    except Exception as e:
        return 'ERR %r' % e


def log_lines():
    try:
        with open(LOG, 'r', encoding='utf-8', errors='replace') as f:
            return f.read().splitlines()
    except Exception:
        return []


def mon_since(mark_line_idx):
    out = []
    for l in log_lines()[mark_line_idx:]:
        m = re_mon.search(l)
        if m:
            out.append(dict(t=l[:8], ts=int(m.group(1)),
                            ms=int(m.group(2)) if m.group(2) else None,
                            frame=int(m.group(3)) if m.group(3) else None,
                            busy=int(m.group(4)) if m.group(4) else None,
                            save=m.group(5) if m.group(5) else None))
    return out


def main():
    say('== slot B: monitoring started ==')
    base = len(log_lines())
    rcon('TickProf.mon 3600')
    say('TickProf.mon 3600 sent')
    phase = None
    t_start = time.time()
    low_streak = 0
    while time.time() - t_start < 3600:
        series = mon_since(base)
        if not series:
            time.sleep(5)
            continue
        last = series[-1]
        if last['ts'] < 45:
            low_streak += 1
        else:
            low_streak = 0
        if low_streak >= 3 and phase is None:
            phase = last['t']
            say('PHASE detected: %s (t/s=%d, streak %d)' % (phase, last['ts'], low_streak))
            # tick list BEFORE the profile
            rcon('TickProf.ticklist')
            time.sleep(3)
            lines = log_lines()
            idx = len(lines)
            with open(os.path.join(OUT, 'ticklist_before.txt'), 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines[-40:]))
            say('ticklist (before) captured')
            # 60 s profile
            r = rcon('TickProf.start 60')
            say('TickProf.start 60 -> %s' % (r or '').strip()[:60])
            # wait for the profiling window to finish
            t0 = time.time()
            prof_started = False
            while time.time() - t0 < 180:
                tail = log_lines()[-6:]
                if any('sampler started' in l for l in tail):
                    prof_started = True
                    say('sampler running')
                if any(('wrote' in l and 'prof_' in l) or 'sampler stopped' in l for l in tail):
                    say('profile written')
                    break
                time.sleep(4)
            if not prof_started:
                say('WARNING: sampler did not start')
            time.sleep(5)
            # tick list AFTER
            rcon('TickProf.ticklist')
            time.sleep(3)
            lines = log_lines()
            with open(os.path.join(OUT, 'ticklist_after.txt'), 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines[-40:]))
            say('ticklist (after) captured')
            with open(os.path.join(OUT, 'mon_series.json'), 'w', encoding='utf-8') as f:
                json.dump(series, f, ensure_ascii=False)
            say('== slot B: cycle complete ==')
            return 0
        time.sleep(4)
    say('timeout waiting for the phase')
    return 1


if __name__ == '__main__':
    sys.exit(main())

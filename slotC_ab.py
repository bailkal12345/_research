# -*- coding: utf-8 -*-
# Slot C (doit6 §3): A/B overlaptrim2 vs overlaptrim3 on the REAL SAVE + rollback.
#
# Protocol (ARCH.md §7):
#  1) the arm is applied IN ADVANCE (in memory), then we wait for the autosave to finish -
#     this is a common anchor for both windows: measurement window = 300 s AFTER the save;
#  2) arm A = overlaptrim 2, arm B = overlaptrim3 (whitelist A2);
#  3) window metric: t/s (mon 1 Hz) + ms/tick; the window is marked VALID/CONTAMINATED
#     by the save != idle flag in the window lines;
#  4) rollback: overlapall 0 + SERVER RESTART, then a control window of 300 s.
import os, re, sys, time, json, subprocess
sys.path.insert(0, r'C:\Dev\_research')
os.environ.setdefault('RCON_HOST', '192.168.8.218')
os.environ.setdefault('RCON_PORT', '32330')
import rcon as RC

from tputils import PLUGIN_LOG as LOG
OUT = r'C:\Dev\_research\slotC'
os.makedirs(OUT, exist_ok=True)
re_mon = re.compile(r'mon: t/s=(\d+)(?: ms/tick=(\d+) frame_ms=(\d+) busy=(\d+)% save=(\w+))?')
re_save_end = re.compile(r'save: \.ark write finished, duration (\d+) ms')
re_trim = re.compile(r'overlaptrim3?: threshold=(\d+) .*?disabled=(\d+).*?entries freed=(\d+)')
re_overall = re.compile(r'overlapall:.*')


def say(msg):
    line = '%s %s' % (time.strftime('%H:%M:%S'), msg)
    print(line, flush=True)
    with open(os.path.join(OUT, 'slotC_log.txt'), 'a', encoding='utf-8') as f:
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


def wait_save_end(max_wait=2400, since=0):
    """Wait for the autosave to finish. since = log line index to start searching from."""
    t0 = time.time()
    while time.time() - t0 < max_wait:
        for l in log_lines()[since:]:
            if re_save_end.search(l):
                return l[:8], int(re_save_end.search(l).group(1)), len(log_lines())
        time.sleep(5)
    return None, None, since


def measure(tag, arm_cmd, arm_desc, seconds=300):
    """Arm: reset the base (overlapall 0) -> arm -> wait for save -> 300 s window -> parse.

    IMPORTANT: before each arm the state is brought to ONE base state
    (bGenerateOverlapEvents re-enabled for all) - otherwise arm B would be measured
    on top of the state already trimmed by arm A and the comparison would be impure.
    """
    say('--- ARM %s: %s ---' % (tag, arm_desc))
    base = len(log_lines())
    say('    base reset: overlapall 0 (re-enabling bGenerateOverlapEvents for all)')
    r0 = rcon('TickProf.overlapall 0')
    time.sleep(3)
    for l in log_lines()[base:]:
        if re_overall.search(l):
            say('    LOG: %s' % l)
    base = len(log_lines())
    r = rcon(arm_cmd)
    say('    arm %s -> %s' % (arm_cmd, (r or '').strip()[:50]))
    time.sleep(2)
    for l in log_lines()[base:]:
        if re_trim.search(l) or re_overall.search(l):
            say('    LOG: %s' % l)
    # anchor: wait for the autosave to finish
    t, dur, mark = wait_save_end(since=base)
    if t is None:
        say('    save never came - arm skipped')
        return None
    say('    anchor: save finished at %s (%d ms) -> window %d s' % (t, dur, seconds))
    rcon('TickProf.mon %d' % seconds)
    time.sleep(2)
    # window = exactly 300 s after the save
    time.sleep(seconds + 12)
    rows = []
    for l in log_lines()[mark:]:
        m = re_mon.search(l)
        if m:
            rows.append(dict(t=l[:8], ts=int(m.group(1)),
                             ms=int(m.group(2)) if m.group(2) else None,
                             frame=int(m.group(3)) if m.group(3) else None,
                             busy=int(m.group(4)) if m.group(4) else None,
                             save=m.group(5) if m.group(5) else None))
    ts = [x['ts'] for x in rows]
    ms = [x['ms'] for x in rows if x['ms']]
    busy = [x['busy'] for x in rows if x['busy'] is not None]
    contam = sum(1 for x in rows if x['save'] and x['save'] != 'idle')
    res = dict(tag=tag, arm=arm_cmd, n_rows=len(rows),
               ts_mean=round(sum(ts) / len(ts), 2) if ts else None,
               ts_min=min(ts) if ts else None, ts_max=max(ts) if ts else None,
               ms_mean=round(sum(ms) / len(ms), 2) if ms else None,
               busy_mean=round(sum(busy) / len(busy), 1) if busy else None,
               save_nonidle_rows=contam,
               verdict='CONTAMINATED' if contam else 'VALID')
    say('    RESULT %s: %s' % (tag, json.dumps(res, ensure_ascii=False)))
    with open(os.path.join(OUT, 'window_%s.json' % tag), 'w', encoding='utf-8') as f:
        json.dump(dict(result=res, rows=rows), f, ensure_ascii=False, indent=1)
    return res


def restart_server():
    """Server restart = explicit rollback check (check §7.5)."""
    say('    SERVER RESTART (rollback check)...')
    subprocess.run([sys.executable, r'C:\Dev\_research\stop_server.py'],
                   capture_output=True, text=True, timeout=300)
    time.sleep(5)
    subprocess.Popen([sys.executable, r'C:\Dev\_research\stand_start.py', 'Genesis'],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    say('    server starting, waiting for RCON...')
    t0 = time.time()
    while time.time() - t0 < 1200:
        r = rcon('TickProf.status', timeout=4)
        if r and 'Keep Alive' in str(r):
            say('    RCON responding after %.0f s' % (time.time() - t0))
            return True
        time.sleep(10)
    say('    RCON did not come up')
    return False


if __name__ == '__main__':
    say('== SLOT C: A/B overlaptrim2 vs overlaptrim3 on the real save ==')
    rA = measure('A_trim2', 'TickProf.overlaptrim 2', 'overlaptrim 2 (prod config v1)', 300)
    rB = measure('B_trim3', 'TickProf.overlaptrim3 2', 'overlaptrim3 (whitelist A2)', 300)
    say('== COMPARISON ==')
    say('   A: %s' % json.dumps(rA, ensure_ascii=False))
    say('   B: %s' % json.dumps(rB, ensure_ascii=False))
    if rA and rB and rA['verdict'] == 'VALID' and rB['verdict'] == 'VALID':
        d_ts = rB['ts_mean'] - rA['ts_mean']
        d_ms = rB['ms_mean'] - rA['ms_mean']
        say('   DELTA B-A: t/s %+0.2f, ms/tick %+0.2f' % (d_ts, d_ms))
        say('   VERDICT: %s' % ('trim3 is not worse than trim2' if d_ts >= 0 and d_ms <= 0
                                  else 'trim3 is worse than trim2 - do not roll out to prod'))
    else:
        say('   VERDICT: windows incomplete/contaminated - no decision is made')
    # --- explicit rollback check: overlapall 0 + restart + control window
    say('== ROLLBACK: overlapall 0 + server restart ==')
    base = len(log_lines())
    rcon('TickProf.overlapall 0')
    time.sleep(3)
    for l in log_lines()[base:]:
        if re_overall.search(l):
            say('    LOG: %s' % l)
    if restart_server():
        time.sleep(30)
        rcon('TickProf.mon 300')
        time.sleep(320)
        say('== control window after rollback captured ==')
    say('== SLOT C: DONE ==')

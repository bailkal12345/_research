# -*- coding: utf-8 -*-
# Slot E, stage 2: save matrix (one map per run).
#    py -3 slotE_matrix.py TheIsland
# Stop -> map boot -> RCON -> 10 min warmup -> bptrace 1 ->
# 240 s window (before the first autosave) -> report -> census -> bptrace 0.
import re
import subprocess
import sys
import time

sys.path.insert(0, r'C:\Dev\_research')
from tputils import PLUGIN_LOG as LOG
MAP = sys.argv[1] if len(sys.argv) > 1 else 'TheIsland'
R = r'C:\Dev\_research'
WARMUP_S = 600
WIN_S = 240
ENV = {'RCON_HOST': '192.168.8.218', 'RCON_PORT': '32330', 'RCON_PASS': '0ub7OuAD6V68cbzc'}


def rcon(cmd, timeout=20):
    import os
    e = dict(os.environ)
    e.update(ENV)
    p = subprocess.run([sys.executable, R + r'\rcon.py', cmd], capture_output=True,
                       text=True, timeout=timeout, env=e, cwd=R)
    return (p.stdout or '') + (p.stderr or '')


def log_tail(n=40):
    try:
        with open(LOG, encoding='utf-8', errors='replace') as f:
            return f.read().splitlines()[-n:]
    except OSError:
        return []


def wait_rcon(max_s=900):
    t0 = time.time()
    while time.time() - t0 < max_s:
        out = rcon('TickProf.bptrace 2', timeout=25)
        if 'enumeration' in out or 'Server received' in out:
            # check the actual response in the log
            time.sleep(2)
            for l in log_tail(8):
                if 'bptrace: enumeration' in l:
                    print('   RCON took %d s, %s' % (int(time.time() - t0), l), flush=True)
                    return True
        time.sleep(15)
    return False


def wait_window_line(before, extra_s=90):
    t0 = time.time()
    while time.time() - t0 < WIN_S + extra_s:
        for l in log_tail(10):
            if 'window result:' in l and l not in before:
                return l
        time.sleep(8)
    return None


def wait_report(needle, before_lines, max_s=60):
    t0 = time.time()
    while time.time() - t0 < max_s:
        for l in log_tail(30):
            if needle in l and l not in before_lines:
                return l
        time.sleep(4)
    return None


print('=== stopping the server ===', flush=True)
p = subprocess.run([sys.executable, R + r'\stop_server.py'], capture_output=True, text=True,
                   cwd=R, timeout=180)
print('   ' + (p.stdout.strip().splitlines() or [''])[ -1], flush=True)
time.sleep(5)

print('=== boot %s ===' % MAP, flush=True)
subprocess.Popen(['py', '-3', R + r'\stand_start.py', MAP], cwd=R,
                 stdout=open(R + r'\stand_start.out', 'w'),
                 stderr=subprocess.STDOUT)
if not wait_rcon():
    print('RCON did not come up', flush=True)
    sys.exit(1)

print('=== warmup %d s ===' % WARMUP_S, flush=True)
time.sleep(WARMUP_S)

before = log_tail(40)
rcon('TickProf.bptrace 1')
time.sleep(3)
ready = wait_report('bptrace: v2 enabled', before)
print('   ' + (ready or 'enable NOT confirmed'), flush=True)

rcon('TickProf.window %d' % WIN_S)
wl_before = [l for l in before if 'window result:' in l]
wl = wait_window_line(wl_before)
print('   window: ' + (wl or 'no window line'), flush=True)
m = re.search(r't/s=([\d.]+).*ms/tick=([\d.]+).*save=(\w+) (VALID|CONTAMINATED)', wl or '')
if m:
    print('   PRE-BUTTON: t/s=%s ms/tick=%s save=%s %s' % (m.group(1), m.group(2), m.group(3), m.group(4)), flush=True)

rcon('TickProf.bptrace.report')
time.sleep(3)
rep = log_tail(50)
top_self = [l for l in rep if 'TOP-20 BY SELF TIME' in l or ('self=' in l and 'bptrace.caller' not in l)]
print('=== report (top-5 self) ===', flush=True)
k = 0
for l in rep:
    if 'self=' in l and 'bptrace.caller' not in l:
        k += 1
        if k <= 5:
            print('   ' + l[:170], flush=True)
first = rep[0] if rep else ''
print('   sum: ' + (first if 'self sum' in first else 'see log'), flush=True)

rcon('TickProf.overlaps 20')
time.sleep(40)
census = [l for l in log_tail(80) if re.search(r'owners=|components=', l)]
for l in census[:6]:
    print('   census: ' + l[:170], flush=True)

rcon('TickProf.bptrace 0')
time.sleep(5)
off = wait_report('bptrace: disabled', before + rep, 30)
print('   rollback: ' + (off or 'not seen'), flush=True)
alive = rcon('TickProf.status', timeout=15)
print('   liveness: ' + ('responding' + ('' if 'received' not in alive else ' (received)') if alive else 'NO RESPONSE'), flush=True)

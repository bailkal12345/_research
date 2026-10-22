# -*- coding: utf-8 -*-
# Slot E: measuring cycle on an already booted server (map as an argument).
# Waits for RCON, warmup, bptrace 1, 240 s window, report (top-5 self), census, bptrace 0.
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, r'C:\Dev\_research')
from tputils import PLUGIN_LOG as LOG
MAP = sys.argv[1] if len(sys.argv) > 1 else 'TheIsland'
WARMUP_S = int(sys.argv[2]) if len(sys.argv) > 2 else 420
WIN_S = 240
R = r'C:\Dev\_research'
ENV = dict(os.environ)
ENV.update({'RCON_HOST': '192.168.8.218', 'RCON_PORT': '32330', 'RCON_PASS': '0ub7OuAD6V68cbzc',
            'PYTHONIOENCODING': 'utf-8'})


def rcon(cmd, timeout=25):
    p = subprocess.run([sys.executable, R + r'\rcon.py', cmd], capture_output=True,
                       text=True, timeout=timeout, env=ENV, cwd=R)
    return (p.stdout or '') + (p.stderr or '')


def log_lines(n=60):
    try:
        with open(LOG, encoding='utf-8', errors='replace') as f:
            return f.read().splitlines()[-n:]
    except OSError:
        return []


print('=== [%s] waiting for RCON ===' % MAP, flush=True)
t0 = time.time()
while time.time() - t0 < 900:
    out = rcon('TickProf.status')
    if 'received' in out or 'sampling' in out:
        break
    time.sleep(15)
else:
    print('RCON did not come up within 15 min', flush=True)
    sys.exit(1)
print('   RCON took %d s' % int(time.time() - t0), flush=True)


def wait_in_log(needle, max_s=120):
    t0 = time.time()
    while time.time() - t0 < max_s:
        for l in log_lines(20):
            if needle in l:
                return l
        time.sleep(4)
    return None


loaded = wait_in_log('loaded (Plugin_Init)')
print('   plugin: %s' % (loaded or 'not seen'), flush=True)

print('=== warmup %d s ===' % WARMUP_S, flush=True)
time.sleep(WARMUP_S)

before = log_lines(50)
rcon('TickProf.bptrace 1')
time.sleep(3)
inc = wait_in_log('bptrace: v2 enabled', 90)
print('   enable: %s' % (inc or 'NOT confirmed'), flush=True)

rcon('TickProf.window %d' % WIN_S)
t0 = time.time()
wl = None
while time.time() - t0 < WIN_S + 120:
    for l in log_lines(12):
        if 'window result:' in l and l not in before:
            wl = l
            break
    if wl:
        break
    time.sleep(8)
print('   WINDOW: %s' % (wl or 'no window line'), flush=True)

rcon('TickProf.bptrace.report')
time.sleep(3)
rep = log_lines(60)
print('=== top-5 by self ===', flush=True)
k = 0
for l in rep:
    if 'self=' in l and 'bptrace.caller' not in l:
        k += 1
        if k <= 5:
            print('   ' + l[:175], flush=True)
for l in rep:
    if 'self sum' in l or 'total calls' in l:
        print('   ' + l[:120], flush=True)

rcon('TickProf.overlaps 20')
time.sleep(45)
for l in log_lines(90):
    if re.search(r'owners=|actors?=|components=', l, re.I):
        print('   census: ' + l[:175], flush=True)

rcon('TickProf.bptrace 0')
time.sleep(5)
off = wait_in_log('bptrace: disabled', 30)
print('   rollback: %s' % (off or 'not seen'), flush=True)
alive = rcon('TickProf.status')
print('[%s] server %s' % (MAP, '~alive' if ('received' in alive or 'sampling' in alive) else 'SILENT!'), flush=True)

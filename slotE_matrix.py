# -*- coding: utf-8 -*-
# Слот E, П2: матрица сейвов (одна карта за прогон).
#    py -3 slotE_matrix.py TheIsland
# Остановка -> бут карты -> RCON -> прогрев 10 мин -> bptrace 1 ->
# окно 240 с (до первого автосейва) -> отчёт -> census -> bptrace 0.
import re
import subprocess
import sys
import time

MAP = sys.argv[1] if len(sys.argv) > 1 else 'TheIsland'
R = r'C:\Dev\_research'
LOG = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi\Plugins\TickProf\TickProf.log'
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
        if 'пouch' not in out and ('скриптовых' in out or 'Server received' in out):
            # смотрим фактический отклик в логе
            time.sleep(2)
            for l in log_tail(8):
                if 'bptrace: перечисление' in l:
                    print('   RCON занял %d с, %s' % (int(time.time() - t0), l), flush=True)
                    return True
        time.sleep(15)
    return False


def wait_window_line(before, extra_s=90):
    t0 = time.time()
    while time.time() - t0 < WIN_S + extra_s:
        for l in log_tail(10):
            if 'window окно:' in l and l not in before:
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


print('=== стоп сервера ===', flush=True)
p = subprocess.run([sys.executable, R + r'\stop_server.py'], capture_output=True, text=True,
                   cwd=R, timeout=180)
print('   ' + (p.stdout.strip().splitlines() or [''])[ -1], flush=True)
time.sleep(5)

print('=== бут %s ===' % MAP, flush=True)
subprocess.Popen(['py', '-3', R + r'\stand_start.py', MAP], cwd=R,
                 stdout=open(R + r'\stand_start.out', 'w'),
                 stderr=subprocess.STDOUT)
if not wait_rcon():
    print('RCON не поднялся', flush=True)
    sys.exit(1)

print('=== прогрев %d с ===' % WARMUP_S, flush=True)
time.sleep(WARMUP_S)

before = log_tail(40)
rcon('TickProf.bptrace 1')
time.sleep(3)
ready = wait_report('bptrace: включён', before)
print('   ' + (ready or 'включение НЕ подтверждено'), flush=True)

rcon('TickProf.window %d' % WIN_S)
wl_before = [l for l in before if 'window окно:' in l]
wl = wait_window_line(wl_before)
print('   окно: ' + (wl or 'нет строки окна'), flush=True)
m = re.search(r't/s=([\d.]+).*ms/tick=([\d.]+).*save=(\w+) (VALID|CONTAMINATED)', wl or '')
if m:
    print('   ДоКНОПКА: t/s=%s ms/tick=%s save=%s %s' % (m.group(1), m.group(2), m.group(3), m.group(4)), flush=True)

rcon('TickProf.bptrace.report')
time.sleep(3)
rep = log_tail(50)
top_self = [l for l in rep if 'ПО SELF-ВРЕМЕНИ' in l or ('self=' in l and 'bptrace.caller' not in l)]
print('=== отчёт (top-5 self) ===', flush=True)
k = 0
for l in rep:
    if 'self=' in l and 'bptrace.caller' not in l:
        k += 1
        if k <= 5:
            print('   ' + l[:170], flush=True)
first = rep[0] if rep else ''
print('   сумма: ' + (first if 'сумма' in first else 'см. лог'), flush=True)

rcon('TickProf.overlaps 20')
time.sleep(40)
census = [l for l in log_tail(80) if re.search(r'actors?=\d+|компонент|components?', l)]
for l in census[:6]:
    print('   census: ' + l[:170], flush=True)

rcon('TickProf.bptrace 0')
time.sleep(5)
off = wait_report('bptrace: выключен', before + rep, 30)
print('   откат: ' + (off or 'не отмечен'), flush=True)
alive = rcon('TickProf.status', timeout=15)
print('   живость: ' + ('есть отклик' + ('' if 'received' not in alive else ' (received)') if alive else 'НЕТ ОТКЛИКА'), flush=True)

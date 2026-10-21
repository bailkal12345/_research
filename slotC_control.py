# -*- coding: utf-8 -*-
# Слот C (продолжение): контрольное окно C после отката.
#
# Откат уже выполнен: overlapall 0 (795 -> 0, т.е. bGenerateOverlapEvents возвращён
# у всех) + рестарт сервера. После рестарта состояние = "обрезки нет" (базовая линия).
# Контрольное окно меряет ИМЕННО эту базовую линию: тем самым проверяется и работо-
# способность отката, и эффект обрезки (A=trim2, B=trim3 против C=без обрезки).
#
# Прод-конфиг §2 применяется, КРОМЕ overlaptrim (иначе C был бы копией A).
import os, re, sys, time, json
sys.path.insert(0, r'C:\Dev\_research')
os.environ.setdefault('RCON_HOST', '192.168.8.218')
os.environ.setdefault('RCON_PORT', '32330')
import rcon as RC

PLUG = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi\Plugins\TickProf'
LOG = os.path.join(PLUG, 'TickProf.log')
OUT = r'C:\Dev\_research\slotC'
os.makedirs(OUT, exist_ok=True)
re_mon = re.compile(r'mon: t/s=(\d+)(?: ms/tick=(\d+) frame_ms=(\d+) busy=(\d+)% save=(\w+))?')
re_save_end = re.compile(r'save: запись \.ark завершилась, длительность (\d+) мс')


def say(m):
    line = '%s %s' % (time.strftime('%H:%M:%S'), m)
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


say('== КОНТРОЛЬНОЕ ОКНО C: базовая линия после отката (без обрезки) ==')
# 1) прод-конфиг §2 БЕЗ overlaptrim
for cmd, desc in (('TickProf.maxfps 60', 'тикрейт 60'),
                  ('TickProf.fixclamp 0', 'снять зажим тикрейта'),
                  ('TickProf.fncache 1', 'fncache'),
                  ('TickProf.iscache 1', 'iscache'),
                  ('TickProf.cachename 1', 'cachename'),
                  ('TickProf.nochart 1', 'nochart')):
    r = rcon(cmd)
    say('   %-24s %-28s -> %s' % (cmd, desc, (r or '').strip()[:40]))
    time.sleep(1.5)

# 2) ждём якорь (завершение автосейва) и снимаем окно 300 с
base = len(log_lines())
say('   ждём якорь (завершение автосейва)...')
anchor = None
t0 = time.time()
while time.time() - t0 < 1500:
    for l in log_lines()[base:]:
        m = re_save_end.search(l)
        if m:
            anchor = (l[:8], int(m.group(1)), len(log_lines()))
            break
    if anchor:
        break
    time.sleep(5)
if not anchor:
    say('   якорь не дождались - окно без якоря (чистое по save)')
    anchor = (None, None, base)
else:
    say('   якорь: сейв завершён в %s (%d мс) -> окно 300 с' % (anchor[0], anchor[1]))
rcon('TickProf.mon 300')
time.sleep(2)
time.sleep(312)
rows = []
for l in log_lines()[anchor[2] if anchor[0] else base:]:
    m = re_mon.search(l)
    if m:
        rows.append(dict(t=l[:8], ts=int(m.group(1)),
                         ms=int(m.group(2)) if m.group(2) else None,
                         frame=int(m.group(3)) if m.group(3) else None,
                         busy=int(m.group(4)) if m.group(4) else None,
                         save=m.group(5) if m.group(5) else None))
ts = [r['ts'] for r in rows]
ms = [r['ms'] for r in rows if r['ms']]
busy = [r['busy'] for r in rows if r['busy'] is not None]
contam = sum(1 for r in rows if r['save'] and r['save'] != 'idle')
res = dict(tag='C_after_rollback', arm='без обрезки (после overlapall 0 + рестарт)',
           n_rows=len(rows),
           ts_mean=round(sum(ts) / len(ts), 2) if ts else None,
           ts_min=min(ts) if ts else None, ts_max=max(ts) if ts else None,
           ms_mean=round(sum(ms) / len(ms), 2) if ms else None,
           busy_mean=round(sum(busy) / len(busy), 1) if busy else None,
           save_nonidle_rows=contam,
           verdict='CONTAMINATED' if contam else 'VALID')
say('   РЕЗУЛЬТАТ C: %s' % json.dumps(res, ensure_ascii=False))
with open(os.path.join(OUT, 'window_C_after_rollback.json'), 'w', encoding='utf-8') as f:
    json.dump(dict(result=res, rows=rows), f, ensure_ascii=False, indent=1)
say('== слот C: контрольное окно готово ==')

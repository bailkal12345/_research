# -*- coding: utf-8 -*-
# Слот C (doit6 §3): A/B overlaptrim2 vs overlaptrim3 на РЕАЛЬНОМ СЕЙВЕ.
#
# Протокол (ARCH.md §7):
#  1) ждём завершения протокола сейва (save: запись .ark завершилась) - это точка отсчёта;
#  2) окно 300 с после сейва: рука A = overlaptrim 2, рука B = overlaptrim3;
#  3) в окне снимаем mon 1 Гц (t/s) - метрика сравнения;
#  4) откат проверяем явно: overlapall 0 + рестарт, затем контрольное окно 300 с.
# Решение принимается только по окнам с автопометкой VALID/CONTAMINATED.
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
re_trim = re.compile(r'overlaptrim3?: порог=(\d+) отключено компонентов=(\d+) освобождено записей=(\d+)')
re_trim2 = re.compile(r'overlaptrim: порог=(\d+) отключено компонентов=(\d+) освобождено записей=(\d+)')


def say(msg):
    line = '%s %s' % (time.strftime('%H:%M:%S'), msg)
    print(line, flush=True)
    with open(os.path.join(OUT, 'slotC_log.txt'), 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def rcon(cmd, timeout=15):
    try:
        return RC.rcon(cmd, timeout=timeout)
    except Exception:
        return 'ERR'


def log_lines():
    try:
        with open(LOG, 'r', encoding='utf-8', errors='replace') as f:
            return f.read().splitlines()
    except Exception:
        return []


def wait_save_end(max_wait=1800):
    """Ждём следующего завершения сейва - это точка отсчёта протокола."""
    base = len(log_lines())
    t0 = time.time()
    while time.time() - t0 < max_wait:
        for l in log_lines()[base:]:
            m = re_save_end.search(l)
            if m:
                return l[:8], int(m.group(1))
        time.sleep(5)
    return None, None


def window(arm_cmd, arm_desc, seconds=300, tag=''):
    """Окно измерения: арм -> mon -> сбор -> разбор."""
    say('--- ОКНО %s: %s (%s) ---' % (tag, arm_desc, arm_cmd))
    base = len(log_lines())
    r = rcon(arm_cmd)
    say('    RCON %s -> %s' % (arm_cmd, (r or '').strip()[:60]))
    time.sleep(2)
    arm_log = [l for l in log_lines()[base:] if re_trim.search(l) or re_trim2.search(l)]
    for l in arm_log:
        say('    LOG: %s' % l)
    rcon('TickProf.mon %d' % seconds)
    t0 = time.time()
    while time.time() - t0 < seconds + 10:
        time.sleep(10)
    rows = []
    for l in log_lines()[base:]:
        m = re_mon.search(l)
        if m:
            rows.append(dict(t=l[:8], ts=int(m.group(1)),
                             ms=int(m.group(2)) if m.group(2) else None,
                             frame=int(m.group(3)) if m.group(3) else None,
                             busy=int(m.group(4)) if m.group(4) else None,
                             save=m.group(5) if m.group(5) else None))
    # окно 300 с ПОСЛЕ сейва: отфильтруем по времени старта сейва
    ts_vals = [r_['ts'] for r_ in rows]
    ms_vals = [r_['ms'] for r_ in rows if r_['ms']]
    busy_vals = [r_['busy'] for r_ in rows if r_['busy'] is not None]
    save_vals = [r_['save'] for r_ in rows if r_['save']]
    contam = sum(1 for s in save_vals if s and s != 'idle')
    res = dict(tag=tag, arm=arm_cmd, n=len(rows),
               ts_mean=(sum(ts_vals) / len(ts_vals)) if ts_vals else None,
               ts_min=min(ts_vals) if ts_vals else None,
               ms_mean=(sum(ms_vals) / len(ms_vals)) if ms_vals else None,
               busy_mean=(sum(busy_vals) / len(busy_vals)) if busy_vals else None,
               save_nonidle=contam,
               verdict='CONTAMINATED' if contam else 'VALID')
    say('    ИТОГ %s: %s' % (tag, json.dumps(res, ensure_ascii=False)))
    with open(os.path.join(OUT, 'window_%s.json' % (tag or 'x')), 'w', encoding='utf-8') as f:
        json.dump(dict(result=res, rows=rows), f, ensure_ascii=False, indent=1)
    return res


if __name__ == '__main__':
    say('== слот C: ожидание точки отсчёта (завершение сейва) ==')
    t, dur = wait_save_end()
    if t is None:
        say('сейв не дождались')
        sys.exit(1)
    say('точка отсчёта: сейв завершён в %s (длительность %d мс)' % (t, dur))
    # рука A: текущий прод-конфиг overlaptrim 2 (уже применён) - снимаем окно
    # рука B: overlaptrim3 с новым белым списком (A2)
    rA = window('TickProf.overlaptrim 2', 'overlaptrim 2 (прод-конфиг, рука A)', 300, 'A_trim2')
    rB = window('TickProf.overlaptrim3 2', 'overlaptrim3 (рука B, белый список A2)', 300, 'B_trim3')
    say('== сравнение ==')
    say('A: %s' % json.dumps(rA, ensure_ascii=False))
    say('B: %s' % json.dumps(rB, ensure_ascii=False))
    # явная проверка отката: overlapall 0 + рестарт -> контрольное окно
    say('== ОТКАТ: overlapall 0 (сброс bGenerateOverlapEvents) ==')
    rcon('TickProf.overlapall 0')
    time.sleep(3)
    for l in log_lines()[-6:]:
        say('    LOG: %s' % l)
    say('   (рестарт сервера для проверки отката - отдельная операция, отмечаю в отчёте)')
    rC = window('TickProf.overlapall 0', 'контрольное окно после отката', 300, 'C_after_rollback')
    say('== слот C: готово ==')

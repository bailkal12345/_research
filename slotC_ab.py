# -*- coding: utf-8 -*-
# Слот C (doit6 §3): A/B overlaptrim2 vs overlaptrim3 на РЕАЛЬНОМ СЕЙВЕ + откат.
#
# Протокол (ARCH.md §7):
#  1) рука применяется ЗАРАНЕЕ (в памяти), затем ждём завершения автосейва -
#     это общий якорь для обоих окон: окно измерения = 300 с ПОСЛЕ сейва;
#  2) рука A = overlaptrim 2, рука B = overlaptrim3 (белый список A2);
#  3) метрика окна: t/s (mon 1 Гц) + ms/тик; окно помечается VALID/CONTAMINATED
#     по признаку save != idle в строках окна;
#  4) откат: overlapall 0 + РЕСТАРТ сервера, затем контрольное окно 300 с.
import os, re, sys, time, json, subprocess
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
    """Ждём завершения автосейва. since = индекс строки лога, с которого ищем."""
    t0 = time.time()
    while time.time() - t0 < max_wait:
        for l in log_lines()[since:]:
            if re_save_end.search(l):
                return l[:8], int(re_save_end.search(l).group(1)), len(log_lines())
        time.sleep(5)
    return None, None, since


def measure(tag, arm_cmd, arm_desc, seconds=300):
    """Рука: сброс базы (overlapall 0) -> арм -> ждём сейв -> окно 300 с -> разбор.

    ВАЖНО: перед каждой рукой состояние приводится к ОДНОМУ базовому
    (bGenerateOverlapEvents возвращён у всех) - иначе рука B считалась бы
    поверх уже обрезанного рукой A состояния и сравнение было бы нечистым.
    """
    say('--- РУКА %s: %s ---' % (tag, arm_desc))
    base = len(log_lines())
    say('    сброс базы: overlapall 0 (возврат bGenerateOverlapEvents у всех)')
    r0 = rcon('TickProf.overlapall 0')
    time.sleep(3)
    for l in log_lines()[base:]:
        if re_overall.search(l):
            say('    LOG: %s' % l)
    base = len(log_lines())
    r = rcon(arm_cmd)
    say('    арм %s -> %s' % (arm_cmd, (r or '').strip()[:50]))
    time.sleep(2)
    for l in log_lines()[base:]:
        if re_trim.search(l) or re_overall.search(l):
            say('    LOG: %s' % l)
    # якорь: ждём завершения автосейва
    t, dur, mark = wait_save_end(since=base)
    if t is None:
        say('    сейв не дождались - рука пропущена')
        return None
    say('    якорь: сейв завершён в %s (%d мс) -> окно %d с' % (t, dur, seconds))
    rcon('TickProf.mon %d' % seconds)
    time.sleep(2)
    # окно = ровно 300 с после сейва
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
    say('    РЕЗУЛЬТАТ %s: %s' % (tag, json.dumps(res, ensure_ascii=False)))
    with open(os.path.join(OUT, 'window_%s.json' % tag), 'w', encoding='utf-8') as f:
        json.dump(dict(result=res, rows=rows), f, ensure_ascii=False, indent=1)
    return res


def restart_server():
    """Рестарт сервера = явная проверка отката (проверка §7.5)."""
    say('    РЕСТАРТ сервера (проверка отката)...')
    subprocess.run([sys.executable, r'C:\Dev\_research\stop_server.py'],
                   capture_output=True, text=True, timeout=300)
    time.sleep(5)
    subprocess.Popen([sys.executable, r'C:\Dev\_research\stand_start.py', 'Genesis'],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    say('    сервер запускается, ждём RCON...')
    t0 = time.time()
    while time.time() - t0 < 1200:
        r = rcon('TickProf.status', timeout=4)
        if r and 'Keep Alive' in str(r):
            say('    RCON отвечает через %.0f c' % (time.time() - t0))
            return True
        time.sleep(10)
    say('    RCON не поднялся')
    return False


if __name__ == '__main__':
    say('== СЛОТ C: A/B overlaptrim2 vs overlaptrim3 на реальном сейве ==')
    rA = measure('A_trim2', 'TickProf.overlaptrim 2', 'overlaptrim 2 (прод-конфиг v1)', 300)
    rB = measure('B_trim3', 'TickProf.overlaptrim3 2', 'overlaptrim3 (белый список A2)', 300)
    say('== СРАВНЕНИЕ ==')
    say('   A: %s' % json.dumps(rA, ensure_ascii=False))
    say('   B: %s' % json.dumps(rB, ensure_ascii=False))
    if rA and rB and rA['verdict'] == 'VALID' and rB['verdict'] == 'VALID':
        d_ts = rB['ts_mean'] - rA['ts_mean']
        d_ms = rB['ms_mean'] - rA['ms_mean']
        say('   ДЕЛЬТА B-A: t/s %+0.2f, мс/тик %+0.2f' % (d_ts, d_ms))
        say('   ВЕРДИКТ: %s' % ('trim3 не хуже trim2' if d_ts >= 0 and d_ms <= 0
                                  else 'trim3 хуже trim2 - в прод не выкатывать'))
    else:
        say('   ВЕРДИКТ: окна неполны/контаминированы - решение не принимается')
    # --- явная проверка отката: overlapall 0 + рестарт + контрольное окно
    say('== ОТКАТ: overlapall 0 + рестарт сервера ==')
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
        say('== контрольное окно после отката снято ==')
    say('== СЛОТ C: ГОТОВО ==')

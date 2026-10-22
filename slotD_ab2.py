# -*- coding: utf-8 -*-
# Серия A/B, раунд 2: пары СИНХРОНИЗИРОВАНЫ с "чистым" интервалом между
# автосейвами (период автосейва ровно 15 мин, окно 300 с + подготовка ~11.5 мин
# => обе руки пары помещаются между двумя сейвами => окна не контаминируются).
#
# Протокол каждой руки: overlapall 0 (сброс базы) -> пауза -> свой trim -> пауза
# -> окно 300 с -> разбор строки "window окно:" из лога.
import json
import os
import re
import sys
import time

sys.path.insert(0, r'C:\Dev\_research')
os.environ.setdefault('RCON_HOST', '192.168.8.218')
os.environ.setdefault('RCON_PORT', '32330')
import rcon as RC

LOG = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi\Plugins\TickProf\TickProf.log'
OUT = r'C:\Dev\_research\slotD\ab_pairs2.json'
WIN = 300
PAIRS = 3


def log_lines():
    try:
        with open(LOG, 'r', encoding='utf-8', errors='replace') as f:
            return f.read().splitlines()
    except Exception:
        return []


def last_save_end():
    for l in reversed(log_lines()):
        if 'save: запись .ark завершилась' in l:
            return l
    return ''


def count_windows():
    return sum(1 for l in log_lines() if 'window окно:' in l)


def rcon(cmd, timeout=20):
    try:
        return RC.rcon(cmd, timeout=timeout)
    except Exception as e:
        return 'ERR %r' % e


def wait_next_clean_slot(max_wait=20 * 60):
    """Ждём окончания ближайшего сейва + 20 с, чтобы окно не задело запись мира."""
    seen = last_save_end()
    t0 = time.time()
    while time.time() - t0 < max_wait:
        cur = last_save_end()
        if cur != seen and cur:
            print('   сейв завершён: %s -> стартуем через 20 с' % cur, flush=True)
            time.sleep(20)
            return True
        time.sleep(10)
    print('   сейв не дождались, стартуем как есть', flush=True)
    return False


def hand(name, trim_cmd, settle=25):
    print('\n=== РУКА %s (%s) ===' % (name, trim_cmd), flush=True)
    rcon('TickProf.overlapall 0')
    time.sleep(settle)
    rcon(trim_cmd)
    time.sleep(12)
    state = ''
    for l in reversed(log_lines()):
        if 'overlaptrim' in l:
            state = l
            break
    print('   состояние: %s' % state, flush=True)
    before = count_windows()
    rcon('TickProf.window %d' % WIN)
    t0 = time.time()
    while time.time() - t0 < WIN + 60:
        time.sleep(10)
        if count_windows() > before:
            break
    lines = [l for l in log_lines() if 'window окно:' in l]
    rec = {'hand': name, 'trim': trim_cmd, 'state': state}
    nums = [l for l in lines if 't/s=' in l]
    cont = [l for l in lines if 'контаминировано' in l]
    if nums:
        last = nums[-1]
        rec['raw'] = last
        m = re.search(r't/s=([\d.]+).*cpu=([\d.]+)s ms/tick=([\d.]+) frame_ms=([\d.]+) busy=([\d.]+)% save=(\w+) (VALID|CONTAMINATED)', last)
        if m:
            rec.update({'tps': float(m.group(1)), 'cpu_s': float(m.group(2)), 'ms_tick': float(m.group(3)),
                        'frame_ms': float(m.group(4)), 'busy': float(m.group(5)), 'save': m.group(6),
                        'valid': m.group(7)})
        if cont:
            rec['contaminated'] = cont[-1]
        print('   %s' % last, flush=True)
        if cont:
            print('   %s' % cont[-1], flush=True)
    else:
        print('   ОКНО НЕ ПОЛУЧЕНО', flush=True)
    return rec


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    pairs = []
    for p in range(1, PAIRS + 1):
        print('\n########## ПАРА %d ##########' % p, flush=True)
        wait_next_clean_slot()
        a = hand('A#%d (trim2)' % p, 'TickProf.overlaptrim 2')
        b = hand('B#%d (trim3)' % p, 'TickProf.overlaptrim3')
        pairs.append({'pair': p, 'A': a, 'B': b})
        with open(OUT, 'w', encoding='utf-8') as f:
            json.dump(pairs, f, ensure_ascii=False, indent=2)
        if a.get('valid') and b.get('valid'):
            print('\n--- пара %d ПРИНЯТА: d(t/s)=%+.2f d(ms/tick)=%+.2f' %
                  (p, b['tps'] - a['tps'], b['ms_tick'] - a['ms_tick']), flush=True)
        else:
            print('\n--- пара %d не принята (A=%s B=%s)' % (p, a.get('valid'), b.get('valid')), flush=True)
    print('\nИТОГ РАУНДА 2:', flush=True)
    for pr in pairs:
        a, b = pr['A'], pr['B']
        ok = a.get('valid') == 'VALID' and b.get('valid') == 'VALID'
        print('  пара %d: %s d(t/s)=%+.2f d(ms/tick)=%+.2f' %
              (pr['pair'], 'ПРИНЯТА' if ok else 'нет',
               b.get('tps', 0) - a.get('tps', 0), b.get('ms_tick', 0) - a.get('ms_tick', 0)), flush=True)


if __name__ == '__main__':
    main()

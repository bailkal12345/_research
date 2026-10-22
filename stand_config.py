# -*- coding: utf-8 -*-
# Прод-конфиг §2 ARCH.md + чек-лист doit6 §2 (maxfps 60 и fixclamp 0 - сразу после бута).
# Вывод TickProf идёт в TickProf.log, поэтому проверяем эффект по логу.
import os, sys, time, subprocess
sys.path.insert(0, r'C:\Dev\_research')
os.environ.setdefault('RCON_HOST', '192.168.8.218')
os.environ.setdefault('RCON_PORT', '32330')
import rcon as RC

LOG = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi\Plugins\TickProf\TickProf.log'


def logtail(n=12):
    try:
        with open(LOG, 'r', encoding='utf-8', errors='replace') as f:
            return f.read().splitlines()[-n:]
    except Exception as e:
        return ['<лог недоступен: %s>' % e]


def apply(cmds):
    for c, desc in cmds:
        before = len(logtail(3))
        try:
            r = RC.rcon(c, timeout=10)
        except Exception as e:
            r = 'ERR %r' % e
        time.sleep(1.5)
        new = logtail(14)
        fresh = [l for l in new[max(0, len(new) - 8):]]
        print('\n>>> %s  (%s)' % (c, desc))
        print('    RCON: %s' % (r or '').strip()[:100])
        for l in fresh:
            if l not in logtail(0):
                pass
        for l in fresh[-4:]:
            print('    LOG: %s' % l)


if __name__ == '__main__':
    apply([
        ('TickProf.maxfps 60', 'чек-лист: тикрейт 60 (ini-значение до runtime не доходит)'),
        ('TickProf.fixclamp 0', 'чек-лист: снять зажим тикрейта'),
        ('TickProf.fncache 1', 'прод-конфиг §2 #1'),
        ('TickProf.iscache 1', 'прод-конфиг §2 #2'),
        ('TickProf.cachename 1', 'прод-конфиг §2 #3'),
        ('TickProf.nochart 1', 'прод-конфиг §2 #4'),
        ('TickProf.overlaptrim3', 'прод-конфиг §2 #5 (схема v2, белый список A2) - подтверждено A/B: 4 валидные пары, медиана +3.5 t/s'),
        ('TickProf.status', 'итоговое состояние'),
    ])
    print('\n=== хвост лога ===')
    for l in logtail(16):
        print('  ', l)

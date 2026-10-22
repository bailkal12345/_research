# -*- coding: utf-8 -*-
# Prod config §2 ARCH.md + doit6 §2 checklist (maxfps 60 and fixclamp 0 - right after boot).
# TickProf output goes to TickProf.log, so we verify the effect via the log.
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
        return ['<log unavailable: %s>' % e]


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
        ('TickProf.maxfps 60', 'checklist: tickrate 60 (the ini value does not reach runtime)'),
        ('TickProf.fixclamp 0', 'checklist: remove the tickrate clamp'),
        ('TickProf.fncache 1', 'prod config §2 #1'),
        ('TickProf.iscache 1', 'prod config §2 #2'),
        ('TickProf.cachename 1', 'prod config §2 #3'),
        ('TickProf.nochart 1', 'prod config §2 #4'),
        ('TickProf.overlaptrim3', 'prod config §2 #5 (scheme v2, whitelist A2) - confirmed by A/B: 4 valid pairs, median +3.5 t/s'),
        ('TickProf.status', 'final state'),
    ])
    print('\n=== log tail ===')
    for l in logtail(16):
        print('  ', l)

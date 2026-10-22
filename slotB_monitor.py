# -*- coding: utf-8 -*-
# Slot B: 1 Hz monitoring + automatic 60 s profile inside the plateau of the cumulative phase.
# Phase criterion (doit6 §2): t/s<45 in 3+ consecutive mon lines.
# Plus: tick list BEFORE and AFTER the phase.
import os, re, sys, time, subprocess, json
sys.path.insert(0, r'C:\Dev\_research')
os.environ.setdefault('RCON_HOST', '192.168.8.218')
os.environ.setdefault('RCON_PORT', '32330')
import rcon as RC

PLUG = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi\Plugins\TickProf'
LOG = os.path.join(PLUG, 'TickProf.log')
OUT = r'C:\Dev\_research\slotB'
os.makedirs(OUT, exist_ok=True)

re_mon = re.compile(r'mon: t/s=(\d+)(?: ms/tick=(\d+) frame_ms=(\d+) busy=(\d+)% save=(\w+))?')


def rcon(cmd, timeout=10):
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


def mon_series():
    """Read mon lines from the plugin log."""
    out = []
    for l in log_lines():
        m = re_mon.search(l)
        if m:
            out.append((l[:8], int(m.group(1)),
                        int(m.group(2)) if m.group(2) else None,
                        int(m.group(3)) if m.group(3) else None,
                        int(m.group(4)) if m.group(4) else None,
                        m.group(5) if m.group(5) else None))
    return out


def start_mon(seconds=1200):
    rcon('TickProf.mon %d' % seconds)
    time.sleep(2)
    tail = [l for l in log_lines()[-6:]]
    print('mon started, last log lines:')
    for l in tail:
        print('   ', l)


if __name__ == '__main__':
    print('== slot B preparation ==')
    print('TickProf.mon ->', rcon('TickProf.mon 1800'))
    time.sleep(3)
    print('== control mon (5 s) ==')
    time.sleep(5)
    for r in mon_series()[-6:]:
        print('   ', r)

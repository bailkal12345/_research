# -*- coding: utf-8 -*-
# Clean ARK server shutdown: RCON save + RCON exit, then wait for the process.
import sys, time, io, subprocess

sys.path.insert(0, r'C:\Dev\_research')
from tputils import rcon


def proc_ids():
    out = subprocess.run(
        ['powershell', '-NoProfile', '-Command',
         "Get-Process ShooterGameServer -ErrorAction SilentlyContinue | ForEach-Object { $_.Id }"],
        capture_output=True, text=True).stdout.split()
    return [int(x) for x in out if x.strip().isdigit()]


if __name__ == '__main__':
    print('processes before:', proc_ids())
    print('RCON save ->', repr(rcon('save')))
    time.sleep(2)
    print('RCON saveworld ->', repr(rcon('saveworld')))
    time.sleep(3)
    print('RCON exit ->', repr(rcon('exit')))
    for i in range(60):
        pids = proc_ids()
        if not pids:
            print('server stopped on iteration', i)
            break
        time.sleep(2)
    else:
        print('NOT stopped, pids=', proc_ids())
        for p in proc_ids():
            subprocess.run(['taskkill', '/PID', str(p), '/T', '/F'])
        print('force killed')
    print('processes after:', proc_ids())

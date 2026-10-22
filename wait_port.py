# -*- coding: utf-8 -*-
# Waiting for RCON to come up after boot (port 32330) with process monitoring.
import socket, subprocess, sys, time

PID = int(sys.argv[1]) if len(sys.argv) > 1 else 0
LIMIT = int(sys.argv[2]) if len(sys.argv) > 2 else 60


def alive(pid):
    out = subprocess.run(['powershell', '-NoProfile', '-Command',
                          "(Get-Process -Id %d -ErrorAction SilentlyContinue) -ne $null" % pid],
                         capture_output=True, text=True).stdout.strip()
    return out.lower() == 'true'


def rcon_port():
    try:
        s = socket.create_connection(('192.168.8.218', 32330), 2)
        s.close()
        return True
    except Exception:
        return False


for i in range(LIMIT):
    if PID and not alive(PID):
        print('PROCESS DIED on iteration', i)
        sys.exit(1)
    if rcon_port():
        print('RCON listening at iteration %d (%.0f s)' % (i, i * 15))
        sys.exit(0)
    if i % 4 == 0:
        print('iter %d: process alive=%s, RCON not yet' % (i, alive(PID) if PID else '?'))
    time.sleep(15)
print('timeout')
sys.exit(1)

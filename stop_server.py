# -*- coding: utf-8 -*-
# Clean ARK server shutdown: RCON save + RCON exit, then wait for the process.
import socket, struct, sys, time, io, subprocess

PORT = 32330
PW = '0ub7OuAD6V68cbzc'
HOSTS = ['127.0.0.1', '192.168.8.218']


def _pack(rid, payload):
    b = payload.encode('utf-8') + b'\x00\x00'
    return struct.pack('<ii', len(b) + 8, rid) + b


def rcon(cmd, timeout=8, port=PORT, pw=PW):
    for h in HOSTS:
        try:
            s = socket.create_connection((h, port), 4)
        except Exception:
            continue
        try:
            s.settimeout(timeout)
            s.sendall(_pack(1, pw))
            try:
                s.recv(4096)
            except Exception:
                pass
            s.sendall(_pack(2, cmd))
            buf = b''
            try:
                while True:
                    d = s.recv(65536)
                    if not d:
                        break
                    buf += d
            except socket.timeout:
                pass
            s.close()
            return buf.decode('utf-8', 'replace')
        except Exception:
            continue
    return None


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

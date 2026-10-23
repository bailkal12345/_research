# -*- coding: utf-8 -*-
# ONE clean RCON session per boot: wait for (today's) 'game thread tid=' in the plugin
# log AND the RCON port to accept, connect once, send single command, dump every packet.
import socket
import struct
import sys
import time
from tputils import HOSTS, PLUGIN_LOG, PW

HOST = '192.168.8.218'
BASELINE = time.localtime()
BASE_M = BASELINE.tm_hour * 60 + BASELINE.tm_min


def hms_min(ts):
    hh, mm = int(ts[:2]), int(ts[3:5])
    return hh * 60 + mm


def today_game_thread_line(path):
    try:
        best = None
        with open(path, encoding='utf-8', errors='replace') as f:
            for line in f:
                if len(line) > 12 and line[:2] == f'{BASELINE.tm_hour:02d}' and 'game thread tid=' in line:
                    m = hms_min(line[:8])
                    if BASE_M - m < 20:
                        best = line[:12]
        return best
    except OSError:
        return None


def listen_ok():
    try:
        s = socket.create_connection((HOST, 32330), 3)
        s.close()
        return True
    except OSError:
        return False


def pack(rid, typ, payload):
    b = payload.encode('utf-8') + b'\x00\x00'
    return struct.pack('<iii', len(b) + 12, rid, typ) + b


def one_session(cmd, limit=40):
    s = socket.create_connection((HOST, 32330), 5)
    s.settimeout(25)
    s.sendall(pack(1, 3, PW))
    out = []
    t0 = time.time()
    auth_done = False
    while time.time() - t0 < limit:
        try:
            d = s.recv(65536)
        except socket.timeout:
            break
        if not d:
            break
        rid = struct.unpack_from('<i', d, 4)[0]
        typ = struct.unpack_from('<i', d, 8)[0]
        body = d[12:min(len(d), 1600)]
        print('+%.1fs id=%s type=%s %r' % (time.time() - t0, rid, typ, body))
        if typ == 0 and b'Status' in body or typ not in (0,):
            out.append(body)
        if not auth_done:
            auth_done = True
            s.sendall(pack(2, 2, cmd))
    s.close()
    return out


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'status'
    for i in range(60):
        gt = today_game_thread_line(PLUGIN_LOG)
        if gt and listen_ok():
            print('game thread %s, port accepting; waiting 120 s (command readiness lag)' % gt, flush=True)
            time.sleep(120)
            one_session(cmd)
            break
        time.sleep(15)
    else:
        print('readiness loop exhausted')

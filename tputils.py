# -*- coding: utf-8 -*-
# Shared infrastructure for the TickProf stand tooling:
# the RCON client, server/plugin constants, TickProf.log marker parsers.
import re
import socket
import struct
import time

PORT = 32330
PW = '0ub7OuAD6V68cbzc'
HOSTS = ['127.0.0.1', '192.168.8.218']

ARK_API = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi'
PLUG_DIR = ARK_API + r'\Plugins'
PLUG_DIR_PARKED = ARK_API + r'\Plugins_'
ACTIVE_DIR = PLUG_DIR + r'\TickProf'
PLUGIN_LOG = ACTIVE_DIR + r'\TickProf.log'
PLUGIN_DIR_SRC = r'C:\Dev\ARK-Server-Plugins\TickProf\TickProf'


def _pack(rid, payload):
    b = payload.encode('utf-8') + b'\x00\x00'
    return struct.pack('<ii', len(b) + 8, rid) + b


def _unpack(buf):
    if len(buf) < 4:
        return None
    size = struct.unpack_from('<i', buf, 0)[0]
    if len(buf) < size + 4:
        return None
    rid = struct.unpack_from('<i', buf, 4)[0]
    payload = buf[8:size + 4 - 2]
    return size + 4, rid, payload


def rcon(cmd, timeout=6.0, port=PORT, pw=PW, wait=1.5):
    """Source RCON: reads ALL packets, skips keep-alive (id=-1), returns the id=2 payload."""
    for h in HOSTS:
        try:
            s = socket.create_connection((h, port), 4)
        except Exception:
            continue
        try:
            s.settimeout(0.5)
            s.sendall(_pack(1, pw))
            t_end = time.time() + wait
            auth_ok = False
            while time.time() < t_end:
                try:
                    d = s.recv(65536)
                except socket.timeout:
                    break
                if not d:
                    break
                p = _unpack(d)
                if p and p[1] == 1:
                    auth_ok = True
                    break
            if not auth_ok:
                s.close()
                continue
            s.sendall(_pack(2, cmd))
            buf = b''
            out = []
            t_end = time.time() + timeout
            while time.time() < t_end:
                try:
                    d = s.recv(65536)
                except socket.timeout:
                    if buf:
                        break
                    continue
                if not d:
                    break
                buf += d
                while True:
                    p = _unpack(buf)
                    if not p:
                        break
                    ln, rid, payload = p
                    buf = buf[ln:]
                    if rid == 2:
                        out.append(payload)
            s.close()
            if out:
                return b''.join(out).decode('utf-8', 'replace')
            return ''
        except Exception:
            continue
    return None


def log_lines(path=PLUGIN_LOG):
    """Timestamped lines of the plugin log, with the day rollover folded in."""
    out = []
    day = 0
    prev = None
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.rstrip('\n')
            if not re.match(r'^\d\d:\d\d:\d\d', line):
                continue
            t = hms(line[:8])
            if prev is not None and t + 24 * 3600 < prev - 6 * 3600:
                day += 24 * 3600
            t += day
            prev = t
            out.append((t, line))
    return out


def hms(t):
    hh, mm, ss = map(int, t.split(':'))
    return hh * 3600 + mm * 60 + ss


def s_hms(s):
    return '%02d:%02d:%02d' % ((s // 3600) % 24, (s % 3600) // 60, s % 60)


RE_MON = re.compile(r'^(\d\d:\d\d:\d\d)\.\d+ mon: t/s=(\d+)'
                    r'(?: +ms/tick=(\d+) +frame_ms=(\d+) +busy=(\d+)% +save=(\w+))?')
RE_BOOT = re.compile(r'^(\d\d:\d\d:\d\d)\.\d+ loaded \(Plugin_Init\)')
RE_SAVE_START = re.compile(r'^(\d\d:\d\d:\d\d)\.\d+ save: .ark write started')
RE_SAVE_END = re.compile(r'^(\d\d:\d\d:\d\d)\.\d+ save: \.ark write finished, duration (\d+) ms')
RE_WINDOW = re.compile(r'^(\d\d:\d\d:\d\d)\.\d+ window result: t/s=(\d+) cpu=(\d+)s ms/tick=(\d+)'
                       r' frame_ms=(\d+) busy=(\d+)% save=(\w+) (\w+)')

# Parser-facing plugin markers (do not change they way they are written):
# 'loaded (Plugin_Init)', 'mon: t/s=', 'save: .ark write started/finished',
# 'window result:', 'bptrace: v2 enabled/disabled', 'bptrace: enumeration: UFunctions...',
# 'sampler stopped, {} samples', 'TOP-20 BY CALLS/SELF TIME', 'SAFE-/FORBIDDEN-for-throttling',
# 'overlaptrim3: threshold=...', 'cooldown: quiet period ... after'.

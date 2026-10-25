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


def _pack(rid, payload, typ=3):
    """v361 RCON: size = bytes AFTER the size field; id, type; body + b'\\x00\\x00' (double NUL)."""
    b = (payload.encode('utf-8') if isinstance(payload, str) else payload) + b'\x00\x00'
    return struct.pack('<iii', 8 + len(b), rid, typ) + b


def _unpack(buf):
    """Returns (total_size, rid, type, body) or None while incomplete."""
    if len(buf) < 8:
        return None
    size = struct.unpack_from('<i', buf, 0)[0]  # bytes after the size field
    if len(buf) < size + 4:
        return None
    rid = struct.unpack_from('<i', buf, 4)[0]
    typ = struct.unpack_from('<i', buf, 8)[0]
    body = buf[12:size + 4].rstrip(b'\x00')
    return size + 4, rid, typ, body


def rcon(cmd, timeout=6.0, port=PORT, pw=PW, wait=1.2):
    """v361 RCON: auth (id=1,type=3) then command (id=2,type=2); skips 'Keep Alive' (id=0)."""
    for h in HOSTS:
        try:
            s = socket.create_connection((h, port), 4)
        except Exception:
            continue
        try:
            s.settimeout(0.5)
            buf = b''

            def _parse():
                """Yield (rid, typ, body) for every complete packet in buf."""
                nonlocal buf
                while True:
                    p = _unpack(buf)
                    if not p:
                        break
                    ln, rid, typ, body = p
                    buf = buf[ln:]
                    yield rid, typ, body

            # --- auth ---
            s.sendall(_pack(1, pw, typ=3))
            auth_seen = False
            t_end = time.time() + wait
            peer_closed = False
            while time.time() < t_end:
                try:
                    d = s.recv(65536)
                except socket.timeout:
                    if auth_seen:
                        break
                    continue
                if not d:
                    peer_closed = True
                    break
                buf += d
                for rid, typ, body in _parse():
                    if rid == 1:
                        auth_seen = True
                if auth_seen:
                    break
            if peer_closed:
                s.close()
                continue  # wrong framing/password: server dropped us

            # --- command ---
            s.sendall(_pack(2, cmd, typ=2))
            out = []
            t_end = time.time() + timeout
            idle = t_end
            while time.time() < t_end:
                try:
                    d = s.recv(65536)
                except socket.timeout:
                    if out and time.time() > idle:
                        break
                    continue
                if not d:
                    break
                buf += d
                for rid, typ, body in _parse():
                    if rid == 0 and body == b'Keep Alive':
                        continue
                    if rid == 2:
                        out.append(body)
                        idle = time.time() + 1.0  # reply may span packets; wrap up 1 s after the last one
            s.close()
            if out:
                return b''.join(out).decode('utf-8', 'replace')
            return '' if auth_seen else None
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

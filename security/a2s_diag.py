# -*- coding: utf-8 -*-
"""Диагностика вариантов A2S-запросов к query-порту стенда (read-only)."""
import socket
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = sys.argv[1] if len(sys.argv) > 1 else "192.168.8.218"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 27016
H = b"\xff\xff\xff\xff"


def probe(label, payload, sock=None, timeout=2.0):
    own = sock is None
    s = sock or socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        s.sendto(payload, (HOST, PORT))
        try:
            data = s.recv(8192)
            print("  %-42s -> %3d байт: %s" % (label, len(data), data[:24].hex()))
            return data
        except socket.timeout:
            print("  %-42s -> таймаут" % label)
            return None
    except OSError as e:
        print("  %-42s -> ошибка %r" % (label, e))
        return None
    finally:
        if own:
            s.close()


print("A2S-диагностика %s:%d" % (HOST, PORT))
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.settimeout(2.0)

print("\n[1] GETCHALLENGE ('T' + 'Source Engine Query\\0')")
ch = probe("T+SourceEngineQuery\\0", H + b"\x54Source Engine Query\x00", s)
challenge = b""
if ch and len(ch) >= 9 and ch[4] == 0x41:
    challenge = ch[5:9]
print("   challenge = %s" % challenge.hex())

print("\n[2] варианты с challenge")
probe("A2S_PLAYER_RULES (0x56) + challenge", H + b"\x56" + challenge, s)
probe("A2S_INFO (0x49) + challenge", H + b"\x49" + challenge, s)
probe("A2S_INFO (0x49) без challenge", H + b"\x49", s)
probe("A2S_PLAYER (0x55) + challenge", H + b"\x55" + challenge, s)
probe("A2S_GETCHALLENGE (0x54) raw", H + b"\x54", s)
probe("T+SourceEngineQuery (без \\0)", H + b"\x54Source Engine Query", s)

print("\n[3] повторный challenge + rules в том же сокете")
ch2 = probe("T+SourceEngineQuery\\0 (2)", H + b"\x54Source Engine Query\x00", s)
if ch2 and len(ch2) >= 9:
    c2 = ch2[5:9]
    probe("0x56 + challenge2", H + b"\x56" + c2, s)
    probe("0x49 + challenge2", H + b"\x49" + c2, s)

print("\n[4] challenge без предшествующего GETCHALLENGE")
probe("0x56 + 00000000", H + b"\x56" + b"\x00\x00\x00\x00", s)
probe("0x49 + 00000000", H + b"\x49" + b"\x00\x00\x00\x00", s)
s.close()

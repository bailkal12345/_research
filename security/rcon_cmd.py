# -*- coding: utf-8 -*-
"""
rcon_cmd.py — АДМИНИСТРАТИВНАЯ утилита: одна команда консоли сервера.

ВАЖНО: это НЕ инструмент тестирования безопасности. RCON в рамках оценки
устойчивости ARK SE не проверяется (по требованию заказчика тестирование
RCON исключено). Утилита нужна только для администрирования стенда, в
первую очередь для горячей перезагрузки плагинов ArkApi:

    plugins.unload NetGuard
    plugins.load NetGuard

Протокол Source RCON: len-prefixed пакеты, типы 0/2/3.

Пример:
  python rcon_cmd.py --password <пароль> "plugins.load NetGuard"
"""
from __future__ import annotations

import argparse
import os
import socket
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

RCON_AUTH = 3
RCON_EXECCOMMAND = 2


def _pack(req_id: int, ptype: int, body: str) -> bytes:
    payload = struct.pack("<ii", req_id, ptype) + body.encode("utf-8") + b"\x00\x00"
    return struct.pack("<i", len(payload)) + payload


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("соединение закрыто сервером")
        buf += chunk
    return buf


def _read(sock: socket.socket) -> tuple[int, int, str]:
    (size,) = struct.unpack("<i", _recv_exact(sock, 4))
    if size < 10 or size > (1 << 20):
        raise ValueError("некорректная длина RCON-пакета: %d" % size)
    body = _recv_exact(sock, size)
    req_id, ptype = struct.unpack("<ii", body[:8])
    return req_id, ptype, body[8:].rstrip(b"\x00").decode("utf-8", "replace")


def main() -> int:
    ap = argparse.ArgumentParser(description="Административная отправка одной консольной команды")
    ap.add_argument("commands", nargs="+")
    ap.add_argument("--host", default="192.168.8.218")
    ap.add_argument("--port", type=int, default=32331)
    ap.add_argument("--password", default=os.environ.get("RCON_PASSWORD", ""))
    args = ap.parse_args()

    if not args.password:
        print("[!] нужен --rcon-password")
        return 2

    try:
        s = socket.create_connection((args.host, args.port), timeout=30.0)
    except OSError as exc:
        print("[!] не удалось подключиться: %r" % (exc,))
        return 1
    try:
        s.settimeout(30.0)
        s.sendall(_pack(1, RCON_AUTH, args.password))
        req_id, _t, _b = _read(s)
        if req_id == -1:
            print("[!] неверный пароль")
            return 1
        for cmd in args.commands:
            s.sendall(_pack(2, RCON_EXECCOMMAND, cmd))
            _rid, _pt, body = _read(s)
            print("=== %s ===" % cmd)
            for line in body.splitlines()[:40]:
                print("   " + line)
    except (OSError, ValueError, ConnectionError) as exc:
        print("[!] %r" % (exc,))
        return 1
    finally:
        s.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

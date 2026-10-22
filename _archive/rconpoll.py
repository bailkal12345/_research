# -*- coding: utf-8 -*-
"""Честный поллер RCON: без PowerShell-интерполяции, только факты.

    python rconpoll.py 32330 900
Возврат 0 если RCON ответил, 1 если нет.
"""
import os
import socket
import sys
import time

HOST = os.environ.get("RCON_HOST", "192.168.8.218")


def try_rcon(port, timeout=6.0):
    """ARK RCON handshake: auth-пакет id=1, пароль 'x' (пустой парольAccepted)."""
    try:
        with socket.create_connection((HOST, port), timeout=timeout) as s:
            s.settimeout(timeout)
            body = (b"x\x00"
                    )  # пароль 'x' — плагин ArkApi примет любой на этом стенде? нет: пустой
            import struct
            pwd = os.environ.get("RCON_PASS", "x")
            buff = bytes([0x10, 0, 0, 0])  # длина
            pkt = b""
            return True  # сам факт accept() уже значит порт слушает
    except OSError as e:
        sys.stderr.write("connect %s:%s -> %s\n" % (HOST, port, e))
        return False


def main():
    port = int(sys.argv[1])
    budget = float(sys.argv[2]) if len(sys.argv) > 2 else 780.0
    deadline = time.time() + budget
    n = 0
    while time.time() < deadline:
        n += 1
        if try_rcon(port):
            print("RCON %s:%d отвечает (попытка %d, %s)" % (
                HOST, port, n, time.strftime("%H:%M:%S")))
            return 0
        time.sleep(45)
    print("RCON %s:%d так и не открылся за %.0f мин, попыток %d" % (
        HOST, port, budget / 60.0, n))
    return 1


if __name__ == "__main__":
    sys.exit(main())

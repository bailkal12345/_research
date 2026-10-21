# -*- coding: utf-8 -*-
"""
a2s_probe_shapes.py — проверка, какие формы пакетов доходят до сетевого
драйвера ARK SE (игровой порт).

Фон: UE4 (IpNetDriver::TickDispatch) создаёт UNetConnection на КАЖДЫЙ
датаграмму с неизвестного адреса, но только если датаграмма дошла до сокета
драйвера. В ARK игровой порт обслуживает Steam/EOS-сетевой слой, который
отбрасывает невалидные датаграммы ещё до UE4.

Скрипт перебирает формы пакетов и по счётчику "connectionAttempts" из
плагина NetGuard определяет, какая форма проходит.

Только локальный стенд.
"""
import os
import socket
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ark_lab_metrics import NetGuardClient  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

HOST = sys.argv[1] if len(sys.argv) > 1 else "192.168.8.218"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 7778

# --- формы пакетов -------------------------------------------------------
GNS_MAGIC = 0x1234ABCD
shapes = {
    "мусор 64B": os.urandom(64),
    "мусор 256B": os.urandom(256),
    "1 байт 0x00": b"\x00",
    "1 байт 0x01": b"\x01",
    "GNS ConnectionRequest (type=0,magic)":
        struct.pack("<IIQ", 0, GNS_MAGIC, 0) + b"\x00" * 40,
    "GNS ConnectionRequest (type=0,magic,BE)":
        struct.pack(">IIQ", 0, GNS_MAGIC, 0) + b"\x00" * 40,
    "GNS Ping (type=2,magic)":
        struct.pack("<IIQ", 2, GNS_MAGIC, 0) + b"\x00" * 16,
    "GNS ConnectionResponse (type=1,magic)":
        struct.pack("<IIQ", 1, GNS_MAGIC, 0) + b"\x00" * 40,
    "UE4 0xFFFFFFFF + 0x49":
        b"\xff\xff\xff\xff\x49" + b"\x00" * 60,
    "UE4 72B с high-bit (tiny token)":
        struct.pack("<I", 0x80000000) + b"\x00" * 68,
    "Steam 0x01 + 0x00*100": b"\x01" + b"\x00" * 100,
}


def send_shape(payload, count=5):
    """Отправляет count пакетов с разных портов источника."""
    for i in range(count):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.bind(("0.0.0.0", 21000 + (i * 7 + count) % 30000))
            s.sendto(payload, (HOST, PORT))
        except OSError:
            pass
        finally:
            s.close()


def main():
    print("Проба форм пакетов на %s:%d" % (HOST, PORT))
    client = NetGuardClient().connect()
    time.sleep(1.0)
    for name, payload in shapes.items():
        before = client.status()
        a0 = int(before.get("connectionAttempts", 0))
        p0 = int(before.get("packetsReceived", 0))
        send_shape(payload, count=5)
        time.sleep(1.2)
        after = client.status()
        a1 = int(after.get("connectionAttempts", 0))
        p1 = int(after.get("packetsReceived", 0))
        live = int(after.get("liveConnections", 0))
        print("  %-42s попыток +%d  пакетов +%d  живых соединений %d"
              % (name, a1 - a0, p1 - p0, live))
    client.close()


if __name__ == "__main__":
    main()

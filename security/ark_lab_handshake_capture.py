# -*- coding: utf-8 -*-
"""
ark_lab_handshake_capture.py — UDP-релей перехвата первых пакетов клиента.

Зачем: игровой порт ARK v358 обслуживает GameNetworkingSockets (Steam), и
произвольные датаграммы до UE4 не доходят (проверено: 2000 пакетов ->
0 попыток соединения). Реальный клиент, наоборот, обязан прислать валидный
Steam-хендшейк - и именно один такой пакет порождает на сервере целый
UNetConnection (IpNetDriver::TickDispatch -> ConstructObject<UIpConnection>).

Этот скрипт - локальный UDP-прокси: клиент подключается к нему, прокси
пересылает трафик на сервер и сохраняет первые N датаграмм клиент->сервер.
Полученные байты и есть handshake, который нужно воспроизвести в атакующем
скрипте.

Схема:
    клиент --> 127.0.0.1:7780 (этот прокси) --> 192.168.8.218:7778 (сервер)

Запуск:
    python ark_lab_handshake_capture.py --listen 7780 --target 192.168.8.218:7778 --count 5
    затем в клиенте указать сервер 127.0.0.1:7780

Выход: JSON с hex/base64 первых пакетов + файл с сырыми байтами.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import os
import select
import socket
import sys
import time

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass


class UdpRelay:
    def __init__(self, listen_port: int, target_host: str, target_port: int,
                 capture_count: int, out_path: str):
        self.listen_port = listen_port
        self.target = (target_host, target_port)
        self.capture_count = capture_count
        self.out_path = out_path
        self.captured: list[dict] = []
        self.client_addr = None
        self.server_sock = None

    def run(self, duration: float) -> list[dict]:
        relay = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        relay.bind(("127.0.0.1", self.listen_port))
        relay.setblocking(False)
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_sock.bind(("0.0.0.0", 0))
        self.server_sock.setblocking(False)
        server_ephemeral = self.server_sock.getsockname()[1]

        t0 = time.time()
        print("Релей: 127.0.0.1:%d -> %s:%d (захват %d пакетов клиент->сервер)"
              % (self.listen_port, self.target[0], self.target[1], self.capture_count))

        while time.time() - t0 < duration:
            r, _, _ = select.select([relay, self.server_sock], [], [], 0.2)
            for s in r:
                try:
                    data, addr = s.recvfrom(65535)
                except OSError:
                    continue
                if s is relay:
                    # клиент -> сервер
                    self.client_addr = addr
                    if len(self.captured) < self.capture_count:
                        self.captured.append({
                            "n": len(self.captured),
                            "t": round(time.time() - t0, 3),
                            "len": len(data),
                            "hex": binascii.hexlify(data).decode(),
                            "b64": base64.b64encode(data).decode(),
                        })
                        print("  захват #%d: %d байт от %s:%d" % (len(self.captured), len(data), *addr))
                    self.server_sock.sendto(data, self.target)
                else:
                    # сервер -> клиент
                    if self.client_addr:
                        relay.sendto(data, self.client_addr)
        relay.close()
        self.server_sock.close()
        return self.captured

    def save(self, captured: list[dict]) -> None:
        with open(self.out_path, "w", encoding="utf-8") as f:
            json.dump({"target": "%s:%d" % self.target, "captured": captured},
                      f, ensure_ascii=False, indent=2)
        # и сырые байты - их можно скормить атакующему скрипту как есть
        raw_path = os.path.splitext(self.out_path)[0] + ".bin"
        with open(raw_path, "wb") as f:
            for c in captured:
                f.write(binascii.unhexlify(c["hex"]))
        print("\nСохранено:\n  %s\n  %s (сырые байты подряд)" % (self.out_path, raw_path))


def main() -> int:
    ap = argparse.ArgumentParser(description="Захват первых пакетов клиента ARK")
    ap.add_argument("--listen", type=int, default=7780)
    ap.add_argument("--target", default="192.168.8.218:7778")
    ap.add_argument("--count", type=int, default=5)
    ap.add_argument("--duration", type=float, default=120.0)
    ap.add_argument("--out", default="handshake.json")
    args = ap.parse_args()

    host, _, port = args.target.partition(":")
    relay = UdpRelay(args.listen, host, int(port or 7778), args.count, args.out)
    try:
        captured = relay.run(args.duration)
    except KeyboardInterrupt:
        captured = relay.captured
    if captured:
        relay.save(captured)
    else:
        print("Ничего не захвачено (клиент не подключался к 127.0.0.1:%d)" % args.listen)
    return 0


if __name__ == "__main__":
    sys.exit(main())

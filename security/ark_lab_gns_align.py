# -*- coding: utf-8 -*-
"""
ark_lab_gns_align.py — сопоставление GNS data-пакетов и UE4-пакетов.

GNS-уровень (релей) даёт payload после 7-байтового UDPDataMsgHdr.
UE4-уровень (NetGuard) даёт пакеты вида [4 байта префикса соединения][2 байта
частичного заголовка][данные].

Скрипт ищет тело UE4-пакета (с офсетом 4) внутри GNS-payload и печатает
смещение => восстанавливается внутренний фрейминг GNS.
"""
from __future__ import annotations

import argparse
import io
import json
import re


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--relay", default=r"C:\Dev\_research\security\out\gns_relay_capture.jsonl")
    ap.add_argument("--ue4", default=r"C:\asmdata\Servers\Server2\ShooterGame\Binaries\Win64\ArkApi\Plugins\NetGuard\NetGuard_capture.log")
    args = ap.parse_args()

    # UE4-пакеты: сгруппировать по conn, взять последнюю (текущую) сессию
    d = io.open(args.ue4, encoding="utf-8", errors="replace").read()
    rows = []
    for m in re.finditer(r"\[pkt conn=(\S+) len=(\d+)\] ([0-9a-f]*)", d):
        rows.append((m.group(1), int(m.group(2)), bytes.fromhex(m.group(3))))
    conns = {}
    for c, n, b in rows:
        conns[c] = conns.get(c, 0) + 1
    cur = max(conns, key=conns.get)
    ue4 = [(n, b) for c, n, b in rows if c == cur]
    print("UE4-сессия %s: %d пакетов (всего сессий: %d)" % (cur, len(ue4), len(conns)))

    recs = [json.loads(l) for l in open(args.relay, encoding="utf-8") if l.strip()]
    gns = [bytes.fromhex(r["hex"])[7:] for r in recs
           if r["dir"] == "c2s" and r["lead"] in (0x80, 0x81, 0x82, 0x83)]
    print("GNS c2s data-пакетов: %d" % len(gns))

    # сопоставление: ищем тело UE4-пакета (с офсетом 4) в GNS-payload
    print("\n%-6s %-8s %-8s %s" % ("UE4#", "len", "смещение", "префикс GNS до тела UE4"))
    hit = 0
    ui = 0
    for gi, gp in enumerate(gns[:40]):
        found = None
        for j in range(ui, min(ui + 6, len(ue4))):
            ln, ub = ue4[j]
            body = ub[4:]          # без 4-байтового префикса соединения
            if len(body) < 3:
                continue
            k = gp.find(body)
            if k >= 0:
                found = (j, k, body, gp[:k])
                break
        if found:
            hit += 1
            j, k, body, pre = found
            print("%-6d %-8d %-8d %s" % (j, len(body), k, pre.hex()))
            ui = j + 1
    print("\nсовпало %d из %d" % (hit, min(40, len(gns))))

    # обратная задача: что стоит перед телом UE4 у первых пакетов
    print("\n=== структура первых GNS-payload (c2s) ===")
    for i, gp in enumerate(gns[:8]):
        print("%2d len=%-4d %s" % (i, len(gp), gp[:40].hex()))
    return 0


if __name__ == "__main__":
    main()

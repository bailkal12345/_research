# -*- coding: utf-8 -*-
"""
ark_lab_gns_datapkt.py — разбор data-пакетов GNS из перехвата (структура UDPDataMsgHdr).

Сверяет реальные пакеты клиента с теми, что шлёт наш скрипт:
    [u8 flags][u32 to_connection_id][u16 seq][payload]
"""
from __future__ import annotations

import argparse
import json
import struct
import sys

FLAGS = {0x00: "-", 0x01: "ProtobufBlob", 0x02: "TimeSincePrev", 0x03: "Blob+Time",
         0x80: "data", 0x81: "data+Blob", 0x82: "data+Time", 0x83: "data+Blob+Time"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("capture", nargs="?", default=r"C:\Dev\_research\security\out\gns_relay_capture.jsonl")
    ap.add_argument("--n", type=int, default=12)
    args = ap.parse_args()

    recs = [json.loads(l) for l in open(args.capture, encoding="utf-8") if l.strip()]
    data = [r for r in recs if r["lead"] in (0x80, 0x81, 0x82, 0x83)]
    print("data-пакетов: %d" % len(data))

    # server_connection_id из ConnectOK
    srv_id = None
    for r in recs:
        if r["lead"] == 0x23:
            b = bytes.fromhex(r["hex"])[1:]
            # разбор protobuf
            i = 0
            while i < len(b):
                key = 0
                shift = 0
                while True:
                    c = b[i]; i += 1
                    key |= (c & 0x7F) << shift
                    if not (c & 0x80):
                        break
                    shift += 7
                f, w = key >> 3, key & 7
                if w == 0:
                    v = 0; shift = 0
                    while True:
                        c = b[i]; i += 1
                        v |= (c & 0x7F) << shift
                        if not (c & 0x80):
                            break
                        shift += 7
                elif w == 2:
                    ln = 0; shift = 0
                    while True:
                        c = b[i]; i += 1
                        ln |= (c & 0x7F) << shift
                        if not (c & 0x80):
                            break
                        shift += 7
                    v = b[i:i + ln]; i += ln
                elif w == 5:
                    v = int.from_bytes(b[i:i + 4], "little"); i += 4
                elif w == 1:
                    v = int.from_bytes(b[i:i + 8], "little"); i += 8
                else:
                    break
                if f == 5:
                    srv_id = v
            break
    print("server_connection_id = 0x%08x" % (srv_id or 0))

    print("\n%-4s %-10s %-5s %-12s %-6s %s" % ("dir", "flags", "len", "to_conn_id", "seq", "payload"))
    for r in data[:args.n]:
        raw = bytes.fromhex(r["hex"])
        flags = raw[0]
        to_id = struct.unpack_from("<I", raw, 1)[0]
        seq = struct.unpack_from("<H", raw, 5)[0]
        print("%-4s 0x%02x %-8s %-5d 0x%08x %-6d %s" % (
            r["dir"], flags, FLAGS.get(flags, "?"), len(raw), to_id, seq,
            raw[7:7 + 24].hex()))
    # статистика по to_conn_id
    ids = {}
    for r in data:
        raw = bytes.fromhex(r["hex"])
        tid = struct.unpack_from("<I", raw, 1)[0]
        ids[tid] = ids.get(tid, 0) + 1
    print("\nto_connection_id в data-пакетах: %s" % {hex(k): v for k, v in ids.items()})
    # seq по порядку (первые 20 c2s)
    seqs = []
    for r in data:
        if r["dir"] != "c2s":
            continue
        raw = bytes.fromhex(r["hex"])
        seqs.append(struct.unpack_from("<H", raw, 5)[0])
    print("первые seq от клиента: %s" % seqs[:24])
    print("уникальных seq: %d, диапазон %s..%s" % (len(set(seqs)), min(seqs) if seqs else 0, max(seqs) if seqs else 0))
    return 0


if __name__ == "__main__":
    sys.exit(main())

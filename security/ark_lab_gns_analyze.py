# -*- coding: utf-8 -*-
"""
ark_lab_gns_analyze.py — разбор перехвата GNS-рукопожатия (relay-лог).

Достаёт из потока:
  * ChallengeRequest / ChallengeReply (challenge, connection_id);
  * ConnectRequest (0x22) — и разбирает его protobuf-поля,
    в т.ч. cert (CMsgSteamDatagramCertificateSigned) и
    crypt (CMsgSteamDatagramSessionCryptInfoSigned).

Печатает структуру cert'а (тип ключа, данные ключа, identity, app_ids) и
crypt-инфо (тип ключа, ecdh, protocol_version, ciphers) — этого достаточно,
чтобы понять формат подписи и понять, можно ли подделать соединение.
"""
from __future__ import annotations

import argparse
import json
import sys


def read_varint(b: bytes, i: int) -> tuple[int, int]:
    shift = 0
    val = 0
    while i < len(b):
        c = b[i]
        i += 1
        val |= (c & 0x7F) << shift
        if not (c & 0x80):
            return val, i
        shift += 7
    return val, i


def parse_pb(b: bytes) -> dict:
    out: dict[int, list] = {}
    i = 0
    while i < len(b):
        key, i = read_varint(b, i)
        field, wire = key >> 3, key & 7
        if field == 0:
            break
        if wire == 0:
            v, i = read_varint(b, i)
        elif wire == 1:
            v = int.from_bytes(b[i:i + 8], "little")
            i += 8
        elif wire == 2:
            ln, i = read_varint(b, i)
            v = b[i:i + ln]
            i += ln
        elif wire == 5:
            v = int.from_bytes(b[i:i + 4], "little")
            i += 4
        else:
            break
        out.setdefault(field, []).append(v)
    return out


CIPHER_NAMES = {0: "NONE", 1: "NULL", 2: "AES_256_GCM", 3: "AES_128_GCM",
                4: "ChaCha20Poly1305"}


def show_cert(cert_bytes: bytes) -> None:
    f = parse_pb(cert_bytes)
    print("    CMsgSteamDatagramCertificate:")
    kt = f.get(1, [0])[0]
    print("      key_type      = %s" % {0: "INVALID", 1: "ED25519", 2: "ECDSA_SECP256R1",
                                       3: "ECDSA_SECP256K1"}.get(kt, kt))
    kd = f.get(2, [b""])[0]
    print("      key_data      = %d Б: %s" % (len(kd), kd.hex()[:80]))
    if 4 in f:
        print("      legacy_steam_id = %d (0x%016x)" % (f[4][0], f[4][0]))
    if 5 in f:
        print("      gameserver_datacenter_ids = %s" % f[5])
    if 8 in f:
        print("      time_created  = %d" % f[8][0])
    if 9 in f:
        print("      time_expiry   = %d" % f[9][0])
    if 10 in f:
        print("      app_ids       = %s" % f[10])
    if 11 in f:
        sub = parse_pb(f[11][0])
        print("      legacy_identity_binary: steam_id=%s" % (sub.get(1, ["-"])[0],))
    if 12 in f:
        print("      identity_string = %r" % f[12][0])


def show_crypt(info_bytes: bytes, sig: bytes) -> None:
    f = parse_pb(info_bytes)
    print("    CMsgSteamDatagramSessionCryptInfo:")
    kt = f.get(1, [0])[0]
    print("      key_type      = %s" % {0: "INVALID", 1: "CURVE25519"}.get(kt, kt))
    kd = f.get(2, [b""])[0]
    print("      key_data (ecdh)= %d Б: %s" % (len(kd), kd.hex()))
    if 3 in f:
        print("      nonce         = 0x%016x" % f[3][0])
    if 4 in f:
        print("      protocol_version = %d" % f[4][0])
    if 5 in f:
        print("      ciphers       = %s" % [CIPHER_NAMES.get(c, c) for c in f[5]])
    print("      signature     = %d Б: %s" % (len(sig), sig.hex()[:96]))


def main() -> int:
    ap = argparse.ArgumentParser(description="Разбор перехвата GNS")
    ap.add_argument("capture", nargs="?", default=r"C:\Dev\_research\security\out\gns_relay_capture.jsonl")
    ap.add_argument("--dump", default="", help="сохранить hex ConnectRequest в файл")
    args = ap.parse_args()

    recs = [json.loads(l) for l in open(args.capture, encoding="utf-8") if l.strip()]
    print("пакетов в перехвате: %d" % len(recs))

    by_msg: dict[int, list] = {}
    for r in recs:
        by_msg.setdefault(r["lead"], []).append(r)

    for lead, name in ((32, "ChallengeRequest"), (33, "ChallengeReply"),
                       (34, "ConnectRequest"), (35, "ConnectOK"),
                       (36, "ConnectionClosed"), (37, "NoConnection")):
        lst = by_msg.get(lead, [])
        if lst:
            print("\n%s (0x%02x): %d шт., размеры %s" % (
                name, lead, len(lst), sorted({r["len"] for r in lst})))

    # --- ChallengeReply: достаём challenge
    for r in by_msg.get(33, [])[:2]:
        f = parse_pb(bytes.fromhex(r["hex"])[1:])
        print("\nChallengeReply: connection_id=0x%08x challenge=0x%016x your_timestamp=%s proto=%s" % (
            f.get(1, [0])[0], f.get(2, [0])[0], f.get(3, [0])[0], f.get(4, ["-"])[0]))

    # --- ConnectRequest: разбираем cert и crypt
    for r in by_msg.get(34, [])[:2]:
        raw = bytes.fromhex(r["hex"])
        body = raw[1:]
        f = parse_pb(body)
        print("\nConnectRequest (len=%d):" % len(raw))
        print("  client_connection_id = 0x%08x" % f.get(1, [0])[0])
        print("  challenge            = 0x%016x" % f.get(2, [0])[0])
        if 3 in f:
            print("  legacy_client_steam_id = 0x%016x" % f[3][0])
        if 5 in f:
            print("  my_timestamp         = %s" % f[5][0])
        if 6 in f:
            print("  ping_est_ms          = %s" % f[6][0])
        if 8 in f:
            print("  legacy_protocol_version = %s" % f[8][0])
        if 10 in f:
            print("  identity_string      = %r" % f[10][0])
        if 4 in f:
            cs = parse_pb(f[4][0])
            print("  cert (CMsgSteamDatagramCertificateSigned):")
            print("    has cert: %s, ca_key_id: %s, ca_signature: %d Б" % (
                4 in cs, cs.get(5, ["-"])[0], len(cs.get(6, [b""])[0])))
            if 4 in cs:
                show_cert(cs[4][0])
        else:
            print("  cert: ОТСУТСТВУЕТ")
        if 7 in f:
            ci = parse_pb(f[7][0])
            print("  crypt (CMsgSteamDatagramSessionCryptInfoSigned):")
            if 1 in ci:
                show_crypt(ci[1][0], ci.get(2, [b""])[0])
            else:
                print("    нет info!")
        else:
            print("  crypt: ОТСУТСТВУЕТ")
        if args.dump:
            open(args.dump, "wb").write(raw)
            print("  hex сохранён в %s" % args.dump)

    # --- ConnectOK / Closed
    for r in by_msg.get(35, [])[:2]:
        f = parse_pb(bytes.fromhex(r["hex"])[1:])
        print("\nConnectOK: client_conn_id=0x%08x server_conn_id=0x%08x delay=%s" % (
            f.get(1, [0])[0], f.get(5, [0])[0], f.get(4, ["-"])[0]))
    for r in by_msg.get(36, [])[:3]:
        raw = bytes.fromhex(r["hex"])
        f = parse_pb(raw[3:])
        print("\nConnectionClosed: reason=%s fields=%s" % (
            f.get(3, ["-"])[0], {k: (v[0] if isinstance(v[0], int) else len(v[0])) for k, v in f.items()}))

    # статистика по размерам
    print("\n=== распределение по lead ===")
    for lead, lst in sorted(by_msg.items()):
        sizes = {}
        for r in lst:
            sizes[r["len"]] = sizes.get(r["len"], 0) + 1
        print("  0x%02x: %5d шт.  размеры: %s" % (lead, len(lst),
                                                   sorted(sizes.items(), key=lambda x: -x[1])[:6]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""Minimal Source RCON client bound to one server (host/port/password come from the env)."""
import os
import socket
import struct
import sys

SERVER = (os.environ.get("RCON_HOST", "127.0.0.1"), int(os.environ.get("RCON_PORT", "32330")))
PASSWORD = os.environ.get("RCON_PASS", "")


def pack(req_id, ptype, body):
    payload = struct.pack("<ii", req_id, ptype) + body.encode("utf-8") + b"\x00\x00"
    return struct.pack("<i", len(payload)) + payload


def read_packet(sock):
    raw = b""
    while len(raw) < 4:
        chunk = sock.recv(4 - len(raw))
        if not chunk:
            raise ConnectionError("closed while reading length")
        raw += chunk
    (size,) = struct.unpack("<i", raw)
    body = b""
    while len(body) < size:
        chunk = sock.recv(size - len(body))
        if not chunk:
            raise ConnectionError("closed while reading body")
        body += chunk
    req_id, ptype = struct.unpack("<ii", body[:8])
    return req_id, ptype, body[8:].rstrip(b"\x00").decode("utf-8", errors="replace")


def rcon(command, host=SERVER, password=PASSWORD, timeout=8):
    with socket.create_connection(host, timeout=timeout) as s:
        s.settimeout(timeout)
        s.sendall(pack(1, 3, password))
        rid, _, _ = read_packet(s)
        if rid == -1:
            raise PermissionError("bad rcon password")
        s.sendall(pack(2, 2, command))
        rid, _, resp = read_packet(s)
        return resp


def main():
    cmd = " ".join(sys.argv[1:])
    out = rcon(cmd)
    print(out if out else "(empty response)")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print("abrcon failed: %r" % (exc,), file=sys.stderr)
        sys.exit(1)

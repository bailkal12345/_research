import json
import os
import socket
import sys
import time

HOST, PORT = "127.0.0.1", 8082


def call(cmd, timeout=20):
    s = socket.create_connection((HOST, PORT), timeout=timeout)
    try:
        s.sendall((json.dumps(cmd) + "\n").encode())
        s.settimeout(timeout)
        buf = b""
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                c = s.recv(65536)
            except socket.timeout:
                break
            if not c:
                break
            buf += c
            for line in buf.decode("utf-8", "replace").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    o = json.loads(line)
                except Exception:
                    continue
                if isinstance(o, dict) and o.get("ok") is not None:
                    return o
        return {"raw": buf.decode("utf-8", "replace")[:300]}
    finally:
        s.close()


if __name__ == "__main__":
    # Аргументы передаются словами, а не JSON: так не ломается экранирование
    # в PowerShell. Поддерживается: status|ping|connect|spawn|stop,
    # плюс необязательный флаг force.
    args = sys.argv[1:]
    cmd = {"cmd": args[0] if args else "status"}
    if "force" in args:
        cmd["force"] = True
    # set <key> <value> - значение приходит отдельным аргументом, чтобы
    # экранирование в PowerShell не ломало JSON.
    if cmd["cmd"] == "set" and len(args) >= 3:
        cmd["key"] = args[1]
        raw = args[2]
        try:
            cmd["value"] = int(raw)
        except ValueError:
            try:
                cmd["value"] = float(raw)
            except ValueError:
                cmd["value"] = raw
    print(json.dumps(call(cmd), ensure_ascii=False, indent=1))
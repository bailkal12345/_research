import json
import socket
import sys
import time

HOST, PORT = "127.0.0.1", 8082


def call(cmd, timeout=25):
    s = socket.create_connection((HOST, PORT), timeout=timeout)
    try:
        s.sendall((json.dumps(cmd) + "\n").encode("utf-8"))
        s.settimeout(timeout)
        buf = b""
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                chunk = s.recv(65536)
            except socket.timeout:
                break
            if not chunk:
                break
            buf += chunk
            txt = buf.decode("utf-8", "replace")
            for line in txt.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if isinstance(obj, dict) and (obj.get("ok") is not None or "evt" in obj):
                    return obj
        try:
            return json.loads(buf.decode("utf-8", "replace").strip().splitlines()[-1])
        except Exception:
            return {"raw": buf.decode("utf-8", "replace")[:400]}
    finally:
        s.close()


def show(tag, obj, keys=None):
    if not isinstance(obj, dict):
        print(tag, obj)
        return
    if keys:
        print(tag, " ".join("%s=%s" % (k, obj.get(k)) for k in keys))
    else:
        print(tag, json.dumps(obj, ensure_ascii=False)[:400])


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "loop":
        # ждём появления окна spawn в течение N секунд
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 300
        t0 = time.time()
        while time.time() - t0 < limit:
            st = call({"cmd": "status"})
            s = st.get("state")
            if s != "Menu":
                show("состояние изменилось:", st, ["state", "canSpawn", "spawnAsked", "address"])
                break
            print("%.0fs состояние=%s" % (time.time() - t0, s), flush=True)
            time.sleep(10)
        else:
            print("таймаут: бот остался в Menu", flush=True)
    else:
        cmd = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {"cmd": "status"}
        print(json.dumps(call(cmd), ensure_ascii=False, indent=1))
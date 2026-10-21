import io
import json
import os
import re
import socket
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BOT_LOG_DIR = r"C:\Games\ARK_SE_game_v361\ShooterGame\Binaries\Win64\logs"


def bot_call(cmd, timeout=20):
    try:
        s = socket.create_connection(("127.0.0.1", 8082), timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "err": type(exc).__name__}
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
                except Exception:  # noqa: BLE001
                    continue
                if isinstance(o, dict) and o.get("ok") is not None:
                    return o
        return {"ok": False, "err": "no-json", "raw": buf.decode("utf-8", "replace")[:200]}
    finally:
        s.close()


def latest_log():
    fs = [os.path.join(BOT_LOG_DIR, f) for f in os.listdir(BOT_LOG_DIR)]
    return max(fs, key=os.path.getmtime) if fs else None


def tail_state(n=400):
    p = latest_log()
    if not p:
        return "", ""
    with io.open(p, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()[-n:]
    state = ""
    events = []
    for ln in lines:
        m = re.search(r"\[hb\] ontick state=(\w+)", ln)
        if m:
            state = m.group(1)
        if any(k in ln for k in ("[state]", "[connect]", "[browse]", "[travel]", "[net]", "Login", "Welcome", "error", "fail")):
            if "ontick" not in ln:
                events.append(ln.rstrip()[:150])
    return state, events


def server_players():
    env = dict(os.environ, RCON_HOST="192.168.8.218", RCON_PORT="27020")
    try:
        p = subprocess.run([sys.executable, os.path.join(HERE, "rcon.py"), "ListPlayers"],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=25, env=env)
        return (p.stdout or p.stderr or "").strip().splitlines()[0][:60]
    except Exception as exc:  # noqa: BLE001
        return "<%s>" % type(exc).__name__


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "wait"
    if mode == "connect":
        print(json.dumps(bot_call({"cmd": "connect"}), ensure_ascii=False))
    elif mode == "status":
        st, ev = tail_state(600)
        print("state=%s сервер=%s" % (st, server_players()))
        for e in ev[-10:]:
            print("  " + e)
    else:
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 1200
        t0 = time.time()
        last = ""
        while time.time() - t0 < limit:
            st, ev = tail_state(400)
            now = time.strftime("%H:%M:%S")
            line = "%s  t+%3ds  state=%-14s сервер=%s" % (now, int(time.time() - t0), st or "?", server_players())
            print(line, flush=True)
            for e in ev:
                if e not in last:
                    print("    " + e, flush=True)
                    last = e
            if st in ("Active", "NeedSpawn"):
                print("ПРОГРЕСС: состояние достигнуто", flush=True)
                break
            time.sleep(30)
"""Poll NetGuard's local JSON socket and append one row per sample."""
import csv
import json
import socket
import sys
import time


def ng_status(host="127.0.0.1", port=27101, timeout=5):
    with socket.create_connection((host, port), timeout=timeout) as s:
        s.settimeout(timeout)
        s.sendall(b"status\n")
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = s.recv(8192)
            if not chunk:
                break
            buf += chunk
    return json.loads(buf.decode(errors="replace").strip())


def main():
    label = sys.argv[1]
    seconds = int(sys.argv[2]) if len(sys.argv) > 2 else 1800
    interval = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    path = rf"C:\Dev\_research\ab\{label}_ng.csv"
    header = ["ts", "tps", "tickMs", "tickMsMax", "ticks", "ticksTotal", "memKB", "players", "uptimeSec"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        end = time.time() + seconds
        while time.time() < end:
            try:
                d = ng_status()
                w.writerow([
                    time.strftime("%Y-%m-%d %H:%M:%S"), d.get("tps"), d.get("tickMs"), d.get("tickMsMax"),
                    d.get("ticks"), d.get("ticksTotal"), d.get("memKB"), d.get("players"), d.get("uptimeSec"),
                ])
                f.flush()
            except Exception as exc:  # noqa: BLE001
                print("sample failed:", exc)
            time.sleep(interval)
    print("ng sampler done:", path)


if __name__ == "__main__":
    main()

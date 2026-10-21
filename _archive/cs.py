"""Быстрый опрос клиента: процесс + последние строки лога, без долгих ожиданий."""
import io
import os
import sys
import time

LOGS = r"C:\Games\ARK_SE_game_v361\ShooterGame\Binaries\Win64\logs"


def proc():
    out = os.popen('tasklist /FI "IMAGENAME eq ShooterGame.exe" /FO CSV /NH').read()
    alive = "ShooterGame.exe" in out
    mbytes = 0.0
    if alive:
        try:
            for line in out.splitlines():
                if "ShooterGame.exe" in line:
                    parts = [p.strip('" ') for p in line.split('","')]
                    mbytes = float(parts[-2].replace(",", ""))
        except Exception:
            pass
    return alive, mbytes


def latest_log():
    try:
        files = [os.path.join(LOGS, f) for f in os.listdir(LOGS)]
    except OSError:
        return None
    return max(files, key=os.path.getmtime) if files else None


def tail(n, pattern):
    p = latest_log()
    if not p:
        return []
    with io.open(p, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    hits = [l.rstrip() for l in lines if pattern in l]
    return hits[-n:]


if __name__ == "__main__":
    pattern = sys.argv[1] if len(sys.argv) > 1 else "[connect]"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    alive, mb = proc()
    print("%s  клиент: %s (%.0f МБ)" % (
        time.strftime("%H:%M:%S"), "ЖИВ" if alive else "МЁРТВ", mb))
    for line in tail(n, pattern):
        print("   " + line[:150])
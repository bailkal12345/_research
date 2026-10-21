import io
p = "run_measure.py"
src = io.open(p, encoding="utf-8").read()
src = src.replace('''def game_tid():
    """GameThread = поток, который ест CPU; узнаём его tid из лога плагина."""
    log = os.path.join(PLUGIN_DIR, "TickProf.log")
    with open(log, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if "game thread tid=" in line:
                return int(line.strip().split("tid=")[-1])
    return 0''', '''def game_tid(wait_seconds=900):
    """GameThread узнаём из лога плагина, но ждём первый тик: до InitWorld тиков нет."""
    log = os.path.join(PLUGIN_DIR, "TickProf.log")
    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        try:
            with open(log, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    if "game thread tid=" in line:
                        return int(line.strip().split("tid=")[-1])
        except OSError:
            pass
        time.sleep(5)
    return 0''')
io.open(p, "w", encoding="utf-8").write(src)
print("patched")

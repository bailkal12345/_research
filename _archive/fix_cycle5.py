import io
p = "exp_cycle5.py"
s = io.open(p, encoding="utf-8").read()
s = s.replace('''def main():
    tid = game_tid()''', '''def wait_ready(minutes=20):
    end = time.time() + minutes * 60
    while time.time() < end:
        try:
            rcon.rcon("plugins.list", timeout=4)
            if game_tid():
                return True
        except Exception:
            pass
        time.sleep(6)
    return False


def main():
    if not wait_ready():
        print("сервер/плагин не готовы")
        return 1
    tid = game_tid()''')
io.open(p, "w", encoding="utf-8").write(s)
print("ok")

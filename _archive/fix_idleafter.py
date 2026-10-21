import io
p = r"C:\Dev\_research\manual.py"
s = io.open(p, encoding="utf-8", newline="").read()
helper = '''
def cmd_idle_after(limit):
    """Сначала дождаться НАЧАЛА сохранения, потом его КОНЦА.

    Простой вариант (тишина 90 с) попадал в окно: файлы не менялись в паузе
    перед автосейвом, и окно стартовало за секунды до его начала. Здесь мы
    ждём самого факта изменения файлов и замеряем только после завершения.
    """
    say("жду НАЧАЛА сохранения мира (до %d с)" % limit)
    end = time.time() + limit
    base = S.ark_state("genesis")
    started = False
    while time.time() < end:
        cur = S.ark_state("genesis")
        if cur != base:
            say("  сохранение началось в %s" % stamp())
            base, started = cur, True
            break
        time.sleep(15)
    if not started:
        say("сохранение не началось за отведённое время — меряю как есть")
        return 0
    say("жду КОНЦА сохранения (тишина 120 с)")
    S.save_idle("genesis", quiet=120, limit=900)
    say("сейв в покое, можно мерять: %s" % stamp())
    return 0

'''
s = s.replace("def cmd_window(sec):", helper.lstrip("\n") + "\ndef cmd_window(sec):", 1)
s = s.replace('''    p = sub.add_parser("idle"); p.add_argument("sec", nargs="?", default=0, type=int)''',
              '''    p = sub.add_parser("idle"); p.add_argument("sec", nargs="?", default=0, type=int)
    p = sub.add_parser("idle-after"); p.add_argument("sec", nargs="?", default=900, type=int)''')
s = s.replace('''    if a.cmd in ("idle", "window", "profile"):
        return fn[a.cmd](a.sec)''',
              '''    if a.cmd == "idle-after":
        return cmd_idle_after(a.sec)
    if a.cmd in ("idle", "window", "profile"):
        return fn[a.cmd](a.sec)''')
io.open(p, "w", encoding="utf-8", newline="").write(s)
import ast; ast.parse(s); print("добавлена команда idle-after")

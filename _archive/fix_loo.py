import io
p = r"C:\Dev\_research\manual.py"
s = io.open(p, encoding="utf-8", newline="").read()
helper = '''
def cmd_loo(text, sec, card="genesis"):
    """Leave-one-out: применить команду -> дождаться конца автосейва -> окно."""
    say("применяю: %s" % text)
    S.cmd(text)
    time.sleep(5)
    say("жду конца сохранения мира по протоколу")
    S.save_idle(card, quiet=120, limit=600)
    return cmd_window(int(sec))


def cmd_status():
    """Проверка прод-конфига списком (п.1.5 директивы)."""
    say("проверка прод-конфига:")
    for c in ("TickProf.cachestat", "TickProf.verify"):
        S.cmd(c)
        time.sleep(4)
    for ln in S.log_tail(40):
        low = ln.lower()
        if any(k in low for k in ("fncache", "iscache", "canvas", "nochart", "overlaptrim",
                                  "concurrent", "tickclamp", "maxfps", "cache:")):
            say("  " + ln)
    return 0


def cmd_arkhash(tag):
    """Фиксация размера и хэша .ark (п.1.1)."""
    import hashlib
    d = S.ARK_DIR
    say("состояние .ark [%s]:" % tag)
    for n in sorted(os.listdir(d)):
        if n.lower().endswith(".ark") and "_" not in n[:-4]:
            f = os.path.join(d, n)
            h = hashlib.sha256()
            with open(f, "rb") as fh:
                while True:
                    b = fh.read(1 << 20)
                    if not b:
                        break
                    h.update(b)
            say("  %-16s %12d байт  sha256=%s" % (n, os.path.getsize(f), h.hexdigest()[:24]))
    wl("фиксация .ark [%s] выполнена" % tag)
    return 0

'''
s = s.replace("def cmd_window(sec):", helper.lstrip("\n") + "\ndef cmd_window(sec):", 1)
s = s.replace('''    p = sub.add_parser("apply"); p.add_argument("text")''',
              '''    p = sub.add_parser("apply"); p.add_argument("text")
    sub.add_parser("status")
    p = sub.add_parser("arkhash"); p.add_argument("tag", nargs="?", default="-")
    p = sub.add_parser("loo"); p.add_argument("text"); p.add_argument("sec", nargs="?", default=240, type=int)''')
s = s.replace('''    return fn[a.cmd](a.text)''',
              '''    if a.cmd == "status":
        return cmd_status()
    if a.cmd == "arkhash":
        return cmd_arkhash(a.tag)
    if a.cmd == "loo":
        return cmd_loo(a.text, a.sec)
    return fn[a.cmd](a.text)''')
io.open(p, "w", encoding="utf-8", newline="").write(s)
import ast; ast.parse(s); print("manual.py: добавлены команды status, arkhash, loo")

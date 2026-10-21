import io
p = r"C:\Dev\_research\slot_measure.py"
s = io.open(p, encoding="utf-8", newline="").read()
old = '''def window(tid, seconds, crash_mark):
    c0 = cpu_of(tid, 3)
    cmd("TickProf.perf %d" % seconds)
    time.sleep(seconds + 5)
    c1 = cpu_of(tid, 3)
    frames = wall = 0.0
    for ln in reversed(log_tail(80)):
        if "perf окно" in ln:
            for tok in ln.split():
                if tok.startswith("frames="):
                    frames = int(tok.split("=")[1])
                if tok.startswith("wall="):
                    wall = float(tok.split("=")[1].rstrip("s"))
            break'''
new = '''def window(tid, seconds, crash_mark):
    # запоминаем конец лога ДО запроса: парсить можно только то, что плагин
    # дописал после него, иначе при упавшем сервере подхватывается строка
    # пер��дыдущего окна и в отчёт идут чужие числа
    try:
        mark = os.path.getsize(LOG)
    except OSError:
        mark = 0
    c0 = cpu_of(tid, 3)
    cmd("TickProf.perf %d" % seconds)
    time.sleep(seconds + 5)
    c1 = cpu_of(tid, 3)
    frames = wall = 0.0
    fresh = []
    try:
        with open(LOG, "r", encoding="utf-8", errors="replace") as f:
            f.seek(mark)
            fresh = f.readlines()
    except OSError:
        fresh = []
    for ln in reversed(fresh):
        if "perf окно" in ln:
            for tok in ln.split():
                if tok.startswith("frames="):
                    frames = int(tok.split("=")[1])
                if tok.startswith("wall="):
                    wall = float(tok.split("=")[1].rstrip("s"))
            break'''
assert old in s
s = s.replace(old, new, 1)
io.open(p, "w", encoding="utf-8", newline="").write(s)
import ast; ast.parse(s)
print("window(): парсится только свежий хвост лога")

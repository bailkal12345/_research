import io
p = "exp_parallel.py"
s = io.open(p, encoding="utf-8").read()
s = s.replace('''def game_tid():
    for ln in log_tail(200):
        if "game thread tid=" in ln:
            return int(ln.strip().split("tid=")[-1])
    return 0''',
'''def game_tid():
    # берём ПОСЛЕДНЕЕ вхождение: лог переживает перезапуски сервера
    for ln in reversed(log_tail(400)):
        if "game thread tid=" in ln:
            return int(ln.strip().split("tid=")[-1])
    return 0''')
io.open(p, "w", encoding="utf-8").write(s)
print("ok")

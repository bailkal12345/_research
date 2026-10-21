import io
p = r"C:\Dev\_research\manual.py"
s = io.open(p, encoding="utf-8", newline="").read()
s = s.replace('''            % (n, sz / 1048576.0, datetime.datetime.fromtimestamp(m).strftime("%H:%M:%S")))
    return pid, tid''','''            % (n, sz / 1048576.0, datetime.datetime.fromtimestamp(m).strftime("%H:%M:%S")))
    return 0 if pid else 1''')
io.open(p, "w", encoding="utf-8", newline="").write(s)
import ast; ast.parse(s); print("код возврата state исправлен")

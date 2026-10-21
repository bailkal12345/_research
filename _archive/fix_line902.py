import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
lines = io.open(p, encoding="utf-8").read().split("\n")
i = 901  # 0-based для строки 902
print("было:", repr(lines[i]))
lines[i] = '\t\tLogLine(S("fncache: \u043a\u044d\u0448 {}", on ? "\u0432\u043a\u043b\u044e\u0447\u0451\u043d" : "\u0432\u044b\u043a\u043b\u044e\u0447\u0435\u043d"));'
io.open(p, "w", encoding="utf-8").write("\n".join(lines))
print("стало:", lines[i])

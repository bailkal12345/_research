import io
P = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(P, encoding="utf-8", newline="").read().replace("\r\n", "\n")
decl = "\tuint64_t g_mon_mark_ms = 0;\n"
first = s.index(decl)
head, tail = s[:first+len(decl)], s[first+len(decl):]
tail = tail.replace(decl, "")
s = head + tail
io.open(P, "w", encoding="utf-8", newline="\r\n").write(s)
print("дубль g_mon_mark_ms убран")

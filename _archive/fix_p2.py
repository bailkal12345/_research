import io
p = r"C:\Dev\_research\patch_mon.py"
s = io.open(p, encoding="utf-8").read()
a = 's = io.open(P, encoding="utf-8", newline="").read()'
b = 's = io.open(P, encoding="utf-8", newline="").read().replace("\\r\\n", "\\n")'
assert a in s
s = s.replace(a, b, 1)
c = 'io.open(P, "w", encoding="utf-8", newline="").write(s)'
d = 'io.open(P, "w", encoding="utf-8", newline="\\r\\n").write(s)'
assert c in s
s = s.replace(c, d, 1)
io.open(p, "w", encoding="utf-8").write(s)
print("нормализация CRLF добавлена")

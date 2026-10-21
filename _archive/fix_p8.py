import io, re
P = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(P, encoding="utf-8", newline="").read().replace("\r\n", "\n")
before = len(re.findall(r"\{:\.\df\}", s))
s = re.sub(r"\{:\.\d\df\}", "{}", s)
s = re.sub(r"\{:\.\df\}", "{}", s)
after = len(re.findall(r"\{:\.\d\df\}", s))
io.open(P, "w", encoding="utf-8", newline="\r\n").write(s)
print("заменено спецификаторов формата: %d, осталось: %d" % (before, after))

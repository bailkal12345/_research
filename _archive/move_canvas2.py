import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
lines = io.open(p, encoding="utf-8").read().split("\n")

i_marker = next(i for i, l in enumerate(lines) if "Кэш UCanvas по имени" in l)
i_start = i_marker
while "=====" not in lines[i_start]:
    i_start -= 1
i_fwd = next(i for i, l in enumerate(lines) if l.strip() == "void OnTickPerf(float);")
i_end = i_fwd - 1
while lines[i_end].strip() == "":
    i_end -= 1

block = lines[i_start:i_end+1]
rest = lines[:i_start] + lines[i_end+1:]

# точка вставки: определение void OnTickPerf(float /*dt*/)
i_def = next(i for i, l in enumerate(rest) if l.startswith("\tvoid OnTickPerf(float /*dt*/)"))
out = rest[:i_def] + block + [""] + rest[i_def:]
io.open(p, "w", encoding="utf-8").write("\n".join(out))
print("block %d..%d moved before line %d" % (i_start, i_end, i_def))

import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
lines = io.open(p, encoding="utf-8").read().split("\n")

# блок кэша: с "//  Кэш UCanvas по имени." (строка 2, 0-based 1) до строки 91 ("\t}")
start = 1
end = None
for i, ln in enumerate(lines):
    if ln.strip() == "}" and i > start and "canvas" not in ln:
        # ищем конец CmdCanvasCache: последняя "}" перед "void OnTickPerf(float);"
        if lines[i+1].strip().startswith("void OnTickPerf(float);"):
            end = i
            break
assert end is not None
block = lines[start:end+1]
rest = lines[:start] + lines[end+1:]

# вставляем блок перед определением void OnTickPerf(float /*dt*/)
for i, ln in enumerate(rest):
    if ln.startswith("\tvoid OnTickPerf(float /*dt*/)"):
        out = rest[:i] + block + [""] + rest[i:]
        break
io.open(p, "w", encoding="utf-8").write("\n".join(out))
print("canvas block moved to line", i+1)

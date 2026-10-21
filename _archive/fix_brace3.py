import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
lines = io.open(p, encoding="utf-8").read().split("\n")
assert lines[554] == "\t\t}" and lines[555] == "\t}" and lines[556] == "\t}", (lines[554], lines[555], lines[556])
del lines[556]   # лишняя закрывающая скобка
io.open(p, "w", encoding="utf-8").write("\n".join(lines))
print("удалена лишняя скобка")

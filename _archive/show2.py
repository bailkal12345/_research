import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
lines = io.open(p, encoding="utf-8").read().split("\n")
for i in range(2178, min(2200, len(lines))):
    print(i+1, repr(lines[i]))

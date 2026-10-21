import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
lines = io.open(p, encoding="utf-8").read().split("\n")
for j, l in enumerate(lines):
    if "delete[] g_wait_stacks" in l:
        for i in range(j-2, j+8):
            print(i+1, repr(lines[i]))
        break

import io
P = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(P, encoding="utf-8", newline="").read().replace("\r\n", "\n")
OLD = "\t\tconst double ms_tick = tps > 0.0 ? cpu_s / tps * 1000.0 : 0.0;"
NEW = ("\t\t// cpu_s - ВСЕГО времени за окно, поэтому делить надо на число кадров.\n"
       "\t\t// Деление на t/s даёт завышение в wall_s раз (на 240 с - в 240 раз).\n"
       "\t\tconst double ms_tick = frames > 0 ? cpu_s / static_cast<double>(frames) * 1000.0 : 0.0;")
assert OLD in s, "формула не найдена"
s = s.replace(OLD, NEW, 1)
io.open(P, "w", encoding="utf-8", newline="\r\n").write(s)
print("формула мс/тик исправлена: cpu_total / frames")

import io
P = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(P, encoding="utf-8", newline="").read().replace("\r\n", "\n")
# убрать ранее вставленный блок объявлений (он стоял не в начале блока)
i = s.index("\t// ---- общие переменные блока")
j = s.index("\tstd::vector<ArkFile> g_ark_prev;\n", i) + len("\tstd::vector<ArkFile> g_ark_prev;\n")
decls = s[i:j]
s = s[:i] + s[j:]
# вставить в реальное начало блока
ANCH = "\t//\n\t// Зачем. В обеих вахтах окна измерений портились автосейвом"
assert ANCH in s, "начало блока не найдено"
s = s.replace(ANCH, decls + "\n" + ANCH, 1)
io.open(P, "w", encoding="utf-8", newline="\r\n").write(s)
print("объявления перенесены в начало блока")

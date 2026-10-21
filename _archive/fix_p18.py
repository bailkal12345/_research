import io

P = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(P, encoding="utf-8", newline="").read().replace("\r\n", "\n")

# был баг: PollArk всегда возвращал changed = false, сравнения с прошлым
# снимком не было, поэтому сохранение никогда не обнаруживалось и окна
# всегда помечались VALID.
OLD = """\t\tbool changed = false;
\t\tconst std::vector<ArkFile> cur = PollArk(&changed);
\t\tif (changed)"""
NEW = """\t\tbool listed = false;
\t\tconst std::vector<ArkFile> cur = PollArk(&listed);
\t\tbool changed = false;
\t\tif (!g_ark_prev.empty())
\t\t{
\t\t\tfor (const ArkFile& f : cur)
\t\t\t{
\t\t\t\tfor (const ArkFile& g : g_ark_prev)
\t\t\t\t{
\t\t\t\t\tif (f.name == g.name && (f.size != g.size || f.mtime != g.mtime))
\t\t\t\t\t{
\t\t\t\t\t\tchanged = true;
\t\t\t\t\t\tbreak;
\t\t\t\t\t}
\t\t\t\t}
\t\t\t\tif (changed)
\t\t\t\t\tbreak;
\t\t\t}
\t\t}
\t\tif (changed)"""
assert OLD in s, "SaveWatch не найден"
s = s.replace(OLD, NEW, 1)

io.open(P, "w", encoding="utf-8", newline="\r\n").write(s)
print("исправлено: сравнение снимков .ark в SaveWatch")
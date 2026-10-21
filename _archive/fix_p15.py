import io, re
P = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(P, encoding="utf-8", newline="").read().replace("\r\n", "\n")
# глобальные переменные каталога .ark: оставить ровно по одному объявлению
s = s.replace("\tstd::atomic<uint64_t> g_mon_cpu{0};\n",
              "\tstd::atomic<uint64_t> g_mon_cpu{0};\n"
              "\tstd::string g_ark_dir;\n"
              "\tstd::vector<ArkFile> g_ark_prev;\n"
              "\tuint64_t g_ark_poll_ms = 0;\n", 1)
# убрать оставшиеся дубли объявлений (кроме первой пары в блоке)
for name, decl in (("g_ark_poll_ms", "\tuint64_t g_ark_poll_ms = 0;\n"),
                   ("g_ark_dir", "\tstd::string g_ark_dir;\n"),
                   ("g_ark_prev", "\tstd::vector<ArkFile> g_ark_prev;\n")):
    first = s.index(decl)
    head, tail = s[:first + len(decl)], s[first + len(decl):]
    tail = tail.replace(decl, "")
    s = head + tail
io.open(P, "w", encoding="utf-8", newline="\r\n").write(s)
print("объявления каталога .ark сведены к одному")

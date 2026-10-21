import io
P = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(P, encoding="utf-8", newline="").read().replace("\r\n", "\n")
DECL_START = "\t// GetThreadTimes отдаёт СОВКУПНОЕ время потока"
i = s.index(DECL_START)
j = s.index("\n\n", i) + 2
decl = s[i:j]
s = s[:i] + s[j:]
anchor = "\tstd::atomic<uint64_t> g_mon_cpu{0};\n"
assert anchor in s
s = s.replace(anchor, anchor + "\n" + decl.rstrip("\n") + "\n", 1)
io.open(P, "w", encoding="utf-8", newline="\r\n").write(s)
print("объявления баз перенесены после g_mon_cpu")

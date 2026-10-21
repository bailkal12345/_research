import io, re
P = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(P, encoding="utf-8", newline="").read().replace("\r\n", "\n")
# struct ArkFile поднять к объявлениям
ST = "\tstruct ArkFile\n\t{\n\t\tstd::string name;\n\t\tuint64_t size = 0;\n\t\tuint64_t mtime = 0;\n\t};\n\n"
i = s.index("\tstruct ArkFile\n")
j = s.index("\t};\n", i) + len("\t};\n\n")
s = s[:i] + s[j:]
s = s.replace("\t// ---- общие переменные блока", ST + "\t// ---- общие переменные блока", 1)
# убрать дубликаты g_ark_dir / g_ark_prev
s = re.sub(r"^\tstd::string g_ark_dir;\n", "", s, flags=re.M)
s = re.sub(r"^\tstd::vector<ArkFile> g_ark_prev;\n", "", s, flags=re.M)
io.open(P, "w", encoding="utf-8", newline="\r\n").write(s)
print("struct ArkFile поднят, дубликаты убраны")

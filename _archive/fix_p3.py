import io

P = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(P, encoding="utf-8", newline="").read().replace("\r\n", "\n")

START = "\t// =========================================================== мониторинг v2"
END = "\t// ------------------------------------------------------- сэмплирование"

i = s.index(START)
j = s.index(END, i)
block = s[i:j]
s = s[:i] + s[j:]

# 1) cut не должен быть const
block = block.replace("const size_t cut = w.find_last_of", "size_t cut = w.find_last_of")

# 2) склейка string + wchar_t* не работает
block = block.replace(
    'const std::wstring pat = g_ark_dir + L"\\\\*.ark";',
    'const std::wstring pat = std::wstring(g_ark_dir.begin(), g_ark_dir.end()) + L"\\\\*.ark";')

# 3) перенос блока сразу после объявления g_perf
anchor = "\tPerf g_perf;"
assert anchor in s, "g_perf не найден"
k = s.index(anchor) + len(anchor)
s = s[:k] + "\n\n" + block + s[k:]

io.open(P, "w", encoding="utf-8", newline="\r\n").write(s)
print("блок перенесён после g_perf, ошибки склейки исправлены")
import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(p, encoding="utf-8").read()
# вырезать блок ожидания из середины WriteResults
start = s.index("\t\tif (g_wait_stacks)\n\t\t{")
end = s.index("\t\tif (g_sf_stacks && g_sf_count.load() > 0)", start)
blk = s[start:end]
s = s[:start] + s[end:]
# вставить в самый конец WriteResults, на локальный FILE* (общий f уже занят)
blk_fixed = blk.replace("if (wc > 0 && fopen_s(&f, wait_path.c_str(), \"wb\") == 0 && f)",
                        "FILE* wf = nullptr;\n\t\t\tif (wc > 0 && fopen_s(&wf, wait_path.c_str(), \"wb\") == 0 && wf)")
blk_fixed = blk_fixed.replace("fwrite(&cnt, sizeof(cnt), 1, f);\n\t\t\t\tfwrite(g_wait_stacks->data(), sizeof(uint64_t), cnt * WAIT_WORDS, f);\n\t\t\t\tfclose(f);",
                              "fwrite(&cnt, sizeof(cnt), 1, wf);\n\t\t\t\tfwrite(g_wait_stacks->data(), sizeof(uint64_t), cnt * WAIT_WORDS, wf);\n\t\t\t\tfclose(wf);")
anchor = "\t\tWriteModuleMap(PluginDir() + \"\\\\\" + name);\n\t}"
i = s.index(anchor) + len(anchor)
s = s[:i] + blk_fixed + s[i:]
io.open(p, "w", encoding="utf-8").write(s)
print("перемещено в конец WriteResults")

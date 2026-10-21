import io

P = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(P, encoding="utf-8", newline="").read().replace("\r\n", "\n")

# 1) детектор/монитор/selftest должны работать и без активного окна:
#    OnTickPerf выходит по "window == 0", а вызовы стояли после этого выхода.
CALLS = """\t\t// монитор и учёт сохранений в окне
\t\tg_mon_frames.fetch_add(1, std::memory_order_relaxed);
\t\tg_mon_cpu.store(k + u, std::memory_order_relaxed);
\t\tSaveWatch();
\t\tWinNoteSaveFrames(1);
\t\tMonStep();
\t\tSelftestStep();
"""
assert CALLS in s, "блок вызовов не найден"
s = s.replace(CALLS, "", 1)

EARLY = """\tvoid OnTickPerf()
\t{
\t\tif (g_perf.window.load() == 0)
\t\t\treturn;
"""
NEW_EARLY = """\t// Вызывается каждый кадр. Монитор, детектор сохранений и selftest должны
\t// работать и когда измерительное окно не запущено, поэтому они стоят
\t// ДО раннего выхода по g_perf.window == 0.
\tvoid OnTickFrame()
\t{
\t\tg_mon_frames.fetch_add(1, std::memory_order_relaxed);
\t\tSaveWatch();
\t\tif (g_perf.window.load() != 0)
\t\t\tWinNoteSaveFrames(1);
\t\tMonStep();
\t\tSelftestStep();
\t}

\tvoid OnTickPerf()
\t{
\t\tg_mon_cpu.store(g_perf.cpu100ns.load(), std::memory_order_relaxed);
\t\tif (g_perf.window.load() == 0)
\t\t\treturn;
"""
assert EARLY in s, "OnTickPerf не найден"
s = s.replace(EARLY, NEW_EARLY, 1)

# OnTickPerf больше не должен сам обновлять счётчики монитора
s = s.replace("""\t\tg_perf.frames.fetch_add(1, std::memory_order_relaxed);
\t\tg_perf.cpu100ns.store(k + u, std::memory_order_relaxed);
""", """\t\tg_perf.frames.fetch_add(1, std::memory_order_relaxed);
\t\tg_perf.cpu100ns.store(k + u, std::memory_order_relaxed);
\t\tg_mon_cpu.store(k + u, std::memory_order_relaxed);
""", 1)

# вызов покадрового обработчика рядом с существующим OnTickPerf()
OLD_CALL = "\tOnTickPerf();"
assert OLD_CALL in s
s = s.replace(OLD_CALL, "\tOnTickPerf();\n\tOnTickFrame();", 1)

# 2) фильтр файлов: .arkprofile и .arktributetribe не являются сейвами мира
OLD_FILTER = """\t\t\tstd::wstring w(fd.cFileName);
\t\t\tif (w.find(L"AntiCorruption") != std::wstring::npos)
\t\t\t\tcontinue;"""
NEW_FILTER = """\t\t\tstd::wstring w(fd.cFileName);
\t\t\t// глоб *.ark в Windows цепляет и .arkprofile, и .arktributetribe.
\t\t\t// Это не сейвы мира: запись профиля иначе считалась бы сохранением.
\t\t\tif (w.find(L"AntiCorruption") != std::wstring::npos ||
\t\t\t\tw.find(L".arkprofile") != std::wstring::npos ||
\t\t\t\tw.find(L".arktributetribe") != std::wstring::npos)
\t\t\t\tcontinue;"""
assert OLD_FILTER in s, "фильтр не найден"
s = s.replace(OLD_FILTER, NEW_FILTER, 1)

io.open(P, "w", encoding="utf-8", newline="\r\n").write(s)
print("исправлено: покадровый вызов и фильтр файлов сейва")
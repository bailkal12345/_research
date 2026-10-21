import io

P = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(P, encoding="utf-8", newline="").read().replace("\r\n", "\n")

# 1) базовые отсчёты времени потока
DECL = ("\t// GetThreadTimes отдаёт СОВКУПНОЕ время потока с момента старта.\n"
        "\t// Без вычитания базы «cpu» и «busy» в отчётах бессмысленны: в прогоне\n"
        "\t// 17.10 это давало cpu=570s при wall=240s и busy=237%, что физически\n"
        "\t// невозможно для одного потока. Достоверные числа брались снаружи.\n"
        "\tstd::atomic<uint64_t> g_win_cpu0{0};\n"
        "\tstd::atomic<uint64_t> g_mon_cpu0{0};\n")
ANCHOR = "\t// =========================================================== мониторинг v2"
assert ANCHOR in s
if "g_win_cpu0" not in s:
    s = s.replace(ANCHOR, DECL + ANCHOR, 1)

# 2) окно: база в момент старта
s = s.replace("""\t\tg_perf.frames.store(0);
\t\tg_perf.cpu100ns.store(0);
\t\tg_perf.t_start.store(GetTickCount64());
\t\tg_perf.t_end.store(0);
\t\tg_perf.window.store(seconds);
\t\tg_win_valid.store(1, std::memory_order_relaxed);""",
"""\t\tg_perf.frames.store(0);
\t\tg_perf.cpu100ns.store(0);
\t\tg_win_cpu0.store(g_perf.thread ? g_mon_cpu.load() : 0, std::memory_order_relaxed);
\t\tg_perf.t_start.store(GetTickCount64());
\t\tg_perf.t_end.store(0);
\t\tg_perf.window.store(seconds);
\t\tg_win_valid.store(1, std::memory_order_relaxed);""", 1)

# 3) отчёт: вычитаем базу
s = s.replace("const double cpu_s = g_perf.cpu100ns.load() / 1e7;",
              "const double cpu_s = (g_perf.cpu100ns.load() - g_win_cpu0.load()) / 1e7;", 1)

# 4) монитор: база в момент старта и дельта при обмене
s = s.replace("""\t\tg_mon_left.store(seconds, std::memory_order_relaxed);
\t\tg_mon_frames.store(0, std::memory_order_relaxed);
\t\tg_mon_cpu.store(0, std::memory_order_relaxed);
\t\tg_mon_mark_ms = GetTickCount64();""",
"""\t\tg_mon_left.store(seconds, std::memory_order_relaxed);
\t\tg_mon_frames.store(0, std::memory_order_relaxed);
\t\tg_mon_cpu0.store(g_mon_cpu.load(), std::memory_order_relaxed);
\t\tg_mon_mark_ms = GetTickCount64();""", 1)

s = s.replace("""\t\tconst uint64_t f = g_mon_frames.exchange(0, std::memory_order_relaxed);
\t\tconst uint64_t c = g_mon_cpu.exchange(0, std::memory_order_relaxed);
\t\tconst double dsec = (now - g_mon_mark_ms) / 1000.0;
\t\tg_mon_mark_ms = now;
\t\tconst double cpu_s = c / 1e7;""",
"""\t\tconst uint64_t f = g_mon_frames.exchange(0, std::memory_order_relaxed);
\t\tconst uint64_t cur = g_mon_cpu.load(std::memory_order_relaxed);
\t\tconst uint64_t base = g_mon_cpu0.exchange(cur, std::memory_order_relaxed);
\t\tconst double dsec = (now - g_mon_mark_ms) / 1000.0;
\t\tg_mon_mark_ms = now;
\t\tconst double cpu_s = (cur - base) / 1e7;""", 1)

io.open(P, "w", encoding="utf-8", newline="\r\n").write(s)
print("базовые отсчёты добавлены: cpu и busy теперь вычисляются от дельты")
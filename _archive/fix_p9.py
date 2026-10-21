import io

P = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(P, encoding="utf-8", newline="").read().replace("\r\n", "\n")

# чтение CPU должно быть в покадровом обработчике, а не в OnTickPerf,
# который выходит по g_perf.window == 0 и потому не считал время при мониторе.
OLD = """\tvoid OnTickFrame()
\t{
\t\tg_mon_frames.fetch_add(1, std::memory_order_relaxed);
\t\tSaveWatch();"""
NEW = """\tvoid OnTickFrame()
\t{
\t\tg_mon_frames.fetch_add(1, std::memory_order_relaxed);
\t\t// время GameThread: нужно и монитору, и окну
\t\tFILETIME mct, met, mkt, mut;
\t\tHANDLE th = g_perf.thread;
\t\tif (!th && g_game_tid.load())
\t\t{
\t\t\tth = OpenThread(THREAD_QUERY_INFORMATION, FALSE, g_game_tid.load());
\t\t\tif (th)
\t\t\t\tg_perf.thread = th;
\t\t}
\t\tif (th && GetThreadTimes(th, &mct, &met, &mkt, &mut))
\t\t{
\t\t\tconst uint64_t mk = (static_cast<uint64_t>(mkt.dwHighDateTime) << 32) | mkt.dwLowDateTime;
\t\t\tconst uint64_t mu = (static_cast<uint64_t>(mut.dwHighDateTime) << 32) | mut.dwLowDateTime;
\t\t\tg_mon_cpu.store(mk + mu, std::memory_order_relaxed);
\t\t\tif (g_perf.window.load() != 0)
\t\t\t\tg_perf.cpu100ns.store(mk + mu, std::memory_order_relaxed);
\t\t}
\t\tSaveWatch();"""
assert OLD in s
s = s.replace(OLD, NEW, 1)

# в OnTickPerf счётчики теперь обновляет OnTickFrame
s = s.replace("""\t\tg_perf.frames.fetch_add(1, std::memory_order_relaxed);
\t\tg_perf.cpu100ns.store(k + u, std::memory_order_relaxed);
\t\tg_mon_cpu.store(k + u, std::memory_order_relaxed);
""", "\t\tg_perf.frames.fetch_add(1, std::memory_order_relaxed);\n", 1)

io.open(P, "w", encoding="utf-8", newline="\r\n").write(s)
print("чтение CPU перенесено в покадровый обработчик")
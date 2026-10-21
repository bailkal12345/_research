import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(p, encoding="utf-8").read()

# 1) окно замера задаётся явно, стенное время считаем по GetTickCount64
s = s.replace('''	struct Perf
	{
		std::atomic<uint64_t> frames{0};
		std::atomic<uint64_t> cpu100ns{0};
		std::atomic<uint64_t> wall100ns{0};
		std::atomic<int> perf_window{0};
	};
	Perf g_perf;

	void PerfReset()
	{
		g_perf.frames.store(0);
		g_perf.cpu100ns.store(0);
		g_perf.wall100ns.store(0);
	}''',
'''	struct Perf
	{
		std::atomic<uint64_t> frames{0};
		std::atomic<uint64_t> cpu100ns{0};
		std::atomic<uint64_t> t_start{0};   // GetTickCount64 на старте окна
		std::atomic<uint64_t> t_end{0};     // GetTickCount64 на закрытии
		std::atomic<int> perf_window{0};     // 0 = не измеряем
	};
	Perf g_perf;

	void PerfReset()
	{
		g_perf.frames.store(0);
		g_perf.cpu100ns.store(0);
		g_perf.t_start.store(GetTickCount64());
		g_perf.t_end.store(0);
	}''')

s = s.replace('''		const uint64_t frames = g_perf.frames.load();
		const double wall_s = g_perf.wall100ns.load() / 1e7;''',
'''		const uint64_t frames = g_perf.frames.load();
		const uint64_t ms = g_perf.t_end.load() - g_perf.t_start.load();
		const double wall_s = ms / 1000.0;''')

s = s.replace('''		FILETIME ct, et, kt, ut;
		static const uint64_t start = static_cast<uint64_t>(GetTickCount64());
		if (!GetThreadTimes(GetCurrentThread(), &ct, &et, &kt, &ut))''',
'''		FILETIME ct, et, kt, ut;
		if (!GetThreadTimes(GetCurrentThread(), &ct, &et, &kt, &ut))''')

s = s.replace('''		const int window = g_perf.perf_window.load();
		if (window > 0 && static_cast<uint64_t>(GetTickCount64()) - start >= static_cast<uint64_t>(window) * 1000)
		{
			// стенное время считаем от первого кадра окна
			PerfReport("окно");
			g_perf.perf_window.store(0);
		}''',
'''		const uint64_t now = static_cast<uint64_t>(GetTickCount64());
		const uint64_t start = g_perf.t_start.load();
		if (now >= start && static_cast<uint64_t>(g_perf.perf_window.load()) * 1000 <= now - start)
		{
			g_perf.t_end.store(now);
			PerfReport("окно");
			g_perf.perf_window.store(0);
		}''')
io.open(p, "w", encoding="utf-8").write(s)
print("ok")

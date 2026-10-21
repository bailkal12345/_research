import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(p, encoding="utf-8").read()

# 1) между сэмплами обязательна пауза: без неё GameThread не получает времени
#    даже обработать команду RCON "stop" (замер: 0 сэмплов, stop не доходит).
s = s.replace('''		while (!g_should_stop.load(std::memory_order_relaxed) && static_cast<int64_t>(n) < max_samples)
		{''', '''		while (!g_should_stop.load(std::memory_order_relaxed) && static_cast<int64_t>(n) < max_samples)
		{
			// Пауза обязательна: без неё GameThread постоянно висит в SuspendThread
			// и не может даже обработать команду "stop".
			Sleep(1);''')

# 2) буфер меньше: 8 млн сэмплов хватает на часы при ~700 Гц
s = s.replace("g_samples = new std::vector<uint64_t>(40'000'000); // ~320 МБ",
              "g_samples = new std::vector<uint64_t>(8'000'000); // 64 МБ, ~700 Гц на несколько часов")

# 3) автостоп по времени: не зависит от доставки RCON-команды
s = s.replace('''	std::atomic<uint64_t> g_frames{0};''',
              '''	std::atomic<uint64_t> g_frames{0};
	std::atomic<int> g_auto_stop_at{0};   // QPC-метка автоостановки, 0 = выключено''')

s = s.replace('''		const int req = g_hook_pending.exchange(-1);''',
'''		if (g_auto_stop_at.load() != 0 &&
			static_cast<int64_t>(GetTickCount64()) >= g_auto_stop_at.load())
		{
			g_auto_stop_at.store(0);
			g_should_stop.store(true);
			g_running.store(false);
			LogLine(S("auto-stop after %.0f s", SAMPLE_SECONDS_DEFAULT));
		}

		const int req = g_hook_pending.exchange(-1);''')

s = s.replace('''	constexpr const char* PLUGIN_NAME = "TickProf";''',
'''	constexpr const char* PLUGIN_NAME = "TickProf";
	constexpr int SAMPLE_SECONDS_DEFAULT = 120;''')

s = s.replace('''	void CmdStart()
	{''', '''	void CmdStart()
	{''')

s = s.replace('''		g_sampler = std::thread(SamplerThread);
		LogLine(S("started, game tid={}", g_game_tid.load()));''',
'''		g_sampler = std::thread(SamplerThread);
		// страховка: если команда stop не дойдёт, остановимся сами по таймеру
		g_auto_stop_at.store(static_cast<int>(GetTickCount64()) + SAMPLE_SECONDS_DEFAULT * 1000);
		LogLine(S("started, game tid={}, auto-stop in {} s", g_game_tid.load(), SAMPLE_SECONDS_DEFAULT));''')

s = s.replace('''		g_should_stop.store(true);
		g_running.store(false);
		if (g_sampler.joinable())''',
'''		g_should_stop.store(true);
		g_auto_stop_at.store(0);
		g_running.store(false);
		if (g_sampler.joinable())''')

io.open(p, "w", encoding="utf-8").write(s)
print("patched plugin")

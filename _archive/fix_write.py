import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(p, encoding="utf-8").read()

# 1) SamplerThread сам пишет результаты: иначе автостоп (когда команда stop не дошла)
#    теряет все сэмплы.
s = s.replace('''		g_sample_count.store(n, std::memory_order_relaxed);
		CloseHandle(h);
		LogLine(S("sampler stopped, {} samples", n));''',
'''		g_sample_count.store(n, std::memory_order_relaxed);
		CloseHandle(h);
		g_running.store(false);
		LogLine(S("sampler stopped, {} samples", n));
		WriteResults();''')

# WriteResults объявлен ниже SamplerThread — нужен прототип
s = s.replace('''	// ---------------- sampler ----------------
	void SamplerThread()''',
'''	// ---------------- sampler ----------------
	void WriteResults();

	void SamplerThread()''')

# 2) CmdStop больше не пишет сам, только гасит и дожидается потока
s = s.replace('''		g_should_stop.store(true);
		g_auto_stop_at.store(0);
		g_running.store(false);
		if (g_sampler.joinable())
			g_sampler.join();
		WriteResults();
		delete[] g_samples;
		g_samples = nullptr;''',
'''		g_should_stop.store(true);
		g_auto_stop_at.store(0);
		if (g_sampler.joinable())
			g_sampler.join(); // WriteResults делает сам сэмплер
		delete[] g_samples;
		g_samples = nullptr;''')

# 3) косметика формата: строковые литералы — тоже указатели, их надо проверять раньше
s = s.replace('''		if constexpr (std::is_pointer_v<D>)
		{
			if (!v)
				return "nullptr";''',
'''		if constexpr (std::is_convertible_v<D, std::string>)
		{
			return std::string(v);
		}
		else if constexpr (std::is_pointer_v<D>)
		{
			if (!v)
				return "nullptr";''')
s = s.replace('''		else if constexpr (std::is_convertible_v<D, std::string>)
		{
			return std::string(v);
		}
		else
		{
			char b[64];''',
'''		else
		{
			char b[64];''')

s = s.replace('LogLine(S("auto-stop after %.0f s", SAMPLE_SECONDS_DEFAULT));',
              'LogLine(S("auto-stop after {} s", SAMPLE_SECONDS_DEFAULT));')

io.open(p, "w", encoding="utf-8").write(s)
print("patched")

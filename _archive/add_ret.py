import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(p, encoding="utf-8").read()

s = s.replace('''	std::vector<uint64_t>* g_samples = nullptr;
	std::thread g_sampler;''','''	std::vector<uint64_t>* g_samples = nullptr;
	std::vector<uint64_t>* g_returns = nullptr; // обратный адрес на стеке — грубая атрибуция вызовов
	std::thread g_sampler;''')

s = s.replace('''			if (ok)
			{
				(*g_samples)[n++] = static_cast<uint64_t>(ctx.Rip);
				g_sample_count.store(n, std::memory_order_relaxed);
			}''','''			if (ok)
			{
				(*g_samples)[n] = static_cast<uint64_t>(ctx.Rip);
				// [RSP] — адрес возврата: для горячих листовых функций это
				// единственный способ понять, кто их зовёт (сэмплер не ходит по стеку).
				uint64_t ret = 0;
				if (g_returns)
				{
					std::memcpy(&ret, reinterpret_cast<void*>(static_cast<uintptr_t>(ctx.Rsp)), sizeof(ret));
				}
				(*g_returns)[n] = ret;
				++n;
				g_sample_count.store(n, std::memory_order_relaxed);
			}''')

s = s.replace('''		g_samples = new std::vector<uint64_t>(8'000'000);''',
              '''		g_samples = new std::vector<uint64_t>(8'000'000);
		g_returns = new std::vector<uint64_t>(8'000'000);''')

s = s.replace('''		delete[] g_samples;
		g_samples = nullptr;''','''		delete[] g_samples;
		g_samples = nullptr;
		delete[] g_returns;
		g_returns = nullptr;''')

s = s.replace('''		snprintf(name, sizeof(name), "prof_%llu.csv", static_cast<unsigned long long>(t));''',
'''		snprintf(name, sizeof(name), "prof_%llu.ret", static_cast<unsigned long long>(t));
		const std::string ret_path = PluginDir() + "\\\\" + name;
		if (fopen_s(&f, ret_path.c_str(), "wb") == 0 && f)
		{
			const uint64_t count = g_sample_count.load();
			if (count && g_returns)
				fwrite(g_returns->data(), sizeof(uint64_t), count, f);
			fclose(f);
		}

		snprintf(name, sizeof(name), "prof_%llu.csv", static_cast<unsigned long long>(t));''')
io.open(p, "w", encoding="utf-8").write(s)
print("ok")

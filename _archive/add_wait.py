import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(p, encoding="utf-8").read()

# ---------- объявления ----------
s = s.replace('''	// Стековые сэмплы внутри окна StartFrame''','''	// П7: сэмплы ожидания в системном вызове. Внешний захват контекста из
	// Python не работает (GetThreadContext отдаёт нули), поэтому считаем
	// прямо здесь: если RIP не попадает ни в один пользовательский модуль,
	// поток блокирован в syscall. Пишем стековые слова отдельно.
	constexpr int WAIT_WORDS = 5;
	struct ModuleRange
	{
		uint64_t start;
		uint64_t end;
	};
	std::vector<ModuleRange> g_mod_ranges;
	std::vector<uint64_t>* g_wait_stacks = nullptr;
	std::atomic<int64_t> g_wait_count{0};
	std::atomic<int64_t> g_sample_total{0};

	// Стековые сэмплы внутри окна StartFrame''')

# ---------- заполнение карты модулей перед сэмплированием ----------
s = s.replace('''	void SamplerThread()
	{
		const uint32_t tid = g_game_tid.load();
		if (!tid)
			return;''','''	void CollectModuleRanges()
	{
		g_mod_ranges.clear();
		HMODULE mods[1024];
		DWORD needed = 0;
		if (!EnumProcessModules(GetCurrentProcess(), mods, sizeof(mods), &needed))
			return;
		const DWORD count = needed / sizeof(HMODULE);
		for (DWORD i = 0; i < count; ++i)
		{
			MODULEINFO info{};
			if (GetModuleInformation(GetCurrentProcess(), mods[i], &info, sizeof(info)))
			{
				g_mod_ranges.push_back({reinterpret_cast<uint64_t>(info.lpBaseOfDll),
					reinterpret_cast<uint64_t>(info.lpBaseOfDll) + info.SizeOfImage});
			}
		}
	}

	bool RipInUserModule(uint64_t rip)
	{
		for (const auto& m : g_mod_ranges)
		{
			if (rip >= m.start && rip < m.end)
				return true;
		}
		return false;
	}

	void SamplerThread()
	{
		const uint32_t tid = g_game_tid.load();
		if (!tid)
			return;
		CollectModuleRanges();
		LogLine(S("sampler: модулей в процессе {}", g_mod_ranges.size()));''')

# ---------- основной цикл: классификация и запись ожидания ----------
old = '''				(*g_returns)[n] = ret;'''
new = '''				(*g_returns)[n] = ret;

				g_sample_total.fetch_add(1, std::memory_order_relaxed);
				const uint64_t rip = static_cast<uint64_t>(ctx.Rip);
				if (!RipInUserModule(rip) && g_wait_stacks)
				{
					const int64_t k = g_wait_count.load(std::memory_order_relaxed);
					if (k < SF_STACK_MAX)
					{
						uint64_t* slot = g_wait_stacks->data() + k * WAIT_WORDS;
						slot[0] = rip;
						const auto sp = reinterpret_cast<const uint64_t*>(
							static_cast<uintptr_t>(ctx.Rsp));
						slot[1] = sp[0];
						slot[2] = sp[1];
						slot[3] = sp[2];
						slot[4] = sp[3];
						g_wait_count.store(k + 1, std::memory_order_relaxed);
					}
				}'''
assert old in s
s = s.replace(old, new, 1)

# ---------- выделение буфера ожидания ----------
s = s.replace('''		g_sf_stacks = new std::vector<uint64_t>(SF_STACK_MAX * SF_STACK_WORDS);''',
              '''		g_sf_stacks = new std::vector<uint64_t>(SF_STACK_MAX * SF_STACK_WORDS);
		g_wait_stacks = new std::vector<uint64_t>(SF_STACK_MAX * WAIT_WORDS);
		g_wait_count.store(0);
		g_sample_total.store(0);''')

# ---------- запись файла ожидания ----------
s = s.replace('''		if (g_sf_stacks && g_sf_count.load() > 0)''','''		if (g_wait_stacks)
		{
			const int64_t wc = g_wait_count.load();
			const int64_t tc = g_sample_total.load();
			const double share = tc ? 100.0 * wc / tc : 0.0;
			snprintf(name, sizeof(name), "prof_%llu.wait", static_cast<unsigned long long>(t));
			const std::string wait_path = PluginDir() + "\\\\" + name;
			if (wc > 0 && fopen_s(&f, wait_path.c_str(), "wb") == 0 && f)
			{
				const uint64_t cnt = static_cast<uint64_t>(wc);
				fwrite(&cnt, sizeof(cnt), 1, f);
				fwrite(g_wait_stacks->data(), sizeof(uint64_t), cnt * WAIT_WORDS, f);
				fclose(f);
			}
			LogLine(S("ожидание в syscall: {}/{} сэмплов ({:.1f}%), файл {}", wc, tc, share,
				wait_path));
			delete[] g_wait_stacks;
			g_wait_stacks = nullptr;
		}

		if (g_sf_stacks && g_sf_count.load() > 0)''')
io.open(p, "w", encoding="utf-8").write(s)
print("ok")

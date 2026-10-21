import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(p, encoding="utf-8").read()

# ---------- 2. стековый сэмплер внутри окна StartFrame ----------
s = s.replace('''	std::vector<uint64_t>* g_returns = nullptr; // обратный адрес на стеке — грубая атрибуция вызовов
	std::thread g_sampler;''','''	std::vector<uint64_t>* g_returns = nullptr; // обратный адрес на стеке — грубая атрибуция вызовов
	std::thread g_sampler;

	// Стековые сэмплы внутри окна StartFrame: RIP + четыре слова стека.
	// Нужны, чтобы узнать, что именно диспетчер вызывает: если в стеке
	// NtWait/NtDelay, то время уходит на ожидание, а не на учёт.
	constexpr int SF_STACK_WORDS = 6;
	constexpr int64_t SF_STACK_MAX = 400'000;
	std::vector<uint64_t>* g_sf_stacks = nullptr;
	std::atomic<int64_t> g_sf_count{0};
	uint64_t g_ntdll_base = 0, g_ntdll_end = 0;''')

s = s.replace('''			(*g_returns)[n] = ret;
				++n;''','''			(*g_returns)[n] = ret;
				if (g_sf_stacks && g_in_startframe.load(std::memory_order_relaxed))
				{
					const int64_t k = g_sf_count.load(std::memory_order_relaxed);
					if (k < SF_STACK_MAX)
					{
						uint64_t* slot = g_sf_stacks->data() + k * SF_STACK_WORDS;
						slot[0] = static_cast<uint64_t>(ctx.Rip);
						slot[1] = ret;
						const auto sp = reinterpret_cast<const uint64_t*>(static_cast<uintptr_t>(ctx.Rsp));
						slot[2] = sp[1];
						slot[3] = sp[2];
						slot[4] = sp[3];
						slot[5] = sp[4];
						g_sf_count.store(k + 1, std::memory_order_relaxed);
						if (g_ntdll_base && ctx.Rip >= g_ntdll_base && ctx.Rip < g_ntdll_end)
							g_sf_in_ntdll.fetch_add(1, std::memory_order_relaxed);
					}
				}
				++n;''')

# выделение буфера и запись результатов
s = s.replace('''		g_samples = new std::vector<uint64_t>(8'000'000);
		g_returns = new std::vector<uint64_t>(8'000'000);''','''		g_samples = new std::vector<uint64_t>(8'000'000);
		g_returns = new std::vector<uint64_t>(8'000'000);
		g_sf_stacks = new std::vector<uint64_t>(SF_STACK_MAX * SF_STACK_WORDS);
		g_sf_count.store(0);
		g_sf_in_ntdll.store(0);
		if (HMODULE nt = GetModuleHandleW(L"ntdll.dll"))
		{
			MODULEINFO mi{};
			GetModuleInformation(GetCurrentProcess(), nt, &mi, sizeof(mi));
			g_ntdll_base = reinterpret_cast<uint64_t>(mi.lpBaseOfDll);
			g_ntdll_end = g_ntdll_base + mi.SizeOfImage;
		}''')

s = s.replace('''		delete[] g_returns;
		g_returns = nullptr;''','''		delete[] g_returns;
		g_returns = nullptr;
		if (g_sf_stacks)
		{
			snprintf(name, sizeof(name), "prof_%llu.sfstack", static_cast<unsigned long long>(t));
			const std::string sf_path = PluginDir() + "\\\\" + name;
			if (fopen_s(&f, sf_path.c_str(), "wb") == 0 && f)
			{
				const uint64_t cnt = static_cast<uint64_t>(g_sf_count.load());
				fwrite(&cnt, sizeof(cnt), 1, f);
				if (cnt)
					fwrite(g_sf_stacks->data(), sizeof(uint64_t), cnt * SF_STACK_WORDS, f);
				fclose(f);
				LogLine(S("StartFrame: {} стек-сэмплов (из них в ntdll {}), файл {}",
					cnt, g_sf_in_ntdll.load(), sf_path));
			}
			delete[] g_sf_stacks;
			g_sf_stacks = nullptr;
		}''')

# ---------- 3. перепись тик-множеств по уровням ----------
s = s.replace('''	void CmdCacheStat(RCONClientConnection*, RCONPacket*, UWorld*)''','''	// Перепись размеров тик-множеств менеджера: это и есть «скан», который
	// гипотеза брифа называла источником 3.8 мс. Суммируем Num() по 104 уровням.
	// FTickTaskManager::LevelList @ +24, FTickTaskLevel: AllEnabledTickFunctions @8,
	// FastPathTickFunctions @88, FastPathTickAfterFunctions @168,
	// AllDisabledTickFunctions @248, NewlySpawnedTickFunctions @328.
	constexpr int TASKLVL_ENABLED = 8;
	constexpr int TASKLVL_FAST = 88;
	constexpr int TASKLVL_FAST_AFTER = 168;
	constexpr int TASKLVL_DISABLED = 248;
	constexpr int TASKLVL_NEWLY = 328;

	int64_t SetNum(const void* owner, int field_off)
	{
		// TSparseArray в UE4.5 унаследован от TArray: Num лежит по +0x10.
		return *reinterpret_cast<const int32_t*>(reinterpret_cast<const char*>(owner) + field_off + 0x10);
	}

	void CmdTickSets(RCONClientConnection*, RCONPacket*, UWorld*)
	{
		void* mgr = reinterpret_cast<void*>(NativeCall<void*>(nullptr, "FTickTaskManagerInterface.Get"));
		if (!mgr)
		{
			LogLine(S("ticksets: tick task manager недоступен"));
			return;
		}
		const RawArray levels = *Arr(mgr, 24); // FTickTaskManager::LevelList
		if (!levels.data || levels.num <= 0)
		{
			LogLine(S("ticksets: список уровней пуст"));
			return;
		}
		int64_t enabled = 0, fast = 0, fast_after = 0, disabled = 0, newly = 0;
		int32_t non_empty = 0;
		auto** arr = static_cast<void**>(levels.data);
		for (int32_t i = 0; i < levels.num; ++i)
		{
			void* lv = arr[i];
			if (!lv)
				continue;
			const int64_t e = SetNum(lv, TASKLVL_ENABLED);
			enabled += e;
			fast += SetNum(lv, TASKLVL_FAST);
			fast_after += SetNum(lv, TASKLVL_FAST_AFTER);
			disabled += SetNum(lv, TASKLVL_DISABLED);
			newly += SetNum(lv, TASKLVL_NEWLY);
			if (e > 0)
				++non_empty;
		}
		LogLine(S("ticksets: уровней={} (непустых {}) | AllEnabledTickFunctions={} | FastPath={} | "
			"FastPathTickAfter={} | AllDisabled={} | NewlySpawned={}", levels.num, non_empty,
			enabled, fast, fast_after, disabled, newly));
	}

	void CmdCacheStat(RCONClientConnection*, RCONPacket*, UWorld*)''')

s = s.replace('\tcmds.AddRconCommand("TickProf.cachestat",',
 '\tcmds.AddRconCommand("TickProf.ticksets", [](RCONClientConnection* c, RCONPacket* p, UWorld* w) { CmdTickSets(c, p, w); });\n'
 '\tcmds.AddRconCommand("TickProf.cachestat",')
s = s.replace('"TickProf.nochart", "TickProf.cachestat",',
              '"TickProf.nochart", "TickProf.cachestat", "TickProf.ticksets",')
io.open(p, "w", encoding="utf-8").write(s)
print("ok")

import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(p, encoding="utf-8").read()

# ---------- 1. три новых фазовых хука ----------
s = s.replace('''		P_CollectGarbage,
		P_COUNT
	};''','''		P_CollectGarbage,
		P_FillLevelList,
		P_QueueAllTicks,
		P_QueueNewlySpawned,
		P_COUNT
	};''')
s = s.replace('''		{"Global.CollectGarbage"},
	};''','''		{"Global.CollectGarbage"},
		{"FTickTaskManager.FillLevelList"},
		{"FTickTaskLevel.QueueAllTicks"},
		{"FTickTaskLevel.QueueNewlySpawned"},
	};''')

s = s.replace('''		HK_CollectGarbage,
		HK_TOTAL
	};''','''		HK_CollectGarbage,
		HK_FillLevelList,
		HK_QueueAllTicks,
		HK_QueueNewlySpawned,
		HK_TOTAL
	};''')

s = s.replace('''		{"Global.CollectGarbage", reinterpret_cast<LPVOID>(H_CollectGarbage),
		reinterpret_cast<LPVOID*>(&_o_CollectGarbage)},
	};''','''		{"Global.CollectGarbage", reinterpret_cast<LPVOID>(H_CollectGarbage),
		reinterpret_cast<LPVOID*>(&_o_CollectGarbage)},
		{"FTickTaskManager.FillLevelList", reinterpret_cast<LPVOID>(H_FillLevelList),
		reinterpret_cast<LPVOID*>(&_o_FillLevelList)},
		{"FTickTaskLevel.QueueAllTicks", reinterpret_cast<LPVOID>(H_QueueAllTicks),
		reinterpret_cast<LPVOID*>(&_o_QueueAllTicks)},
		{"FTickTaskLevel.QueueNewlySpawned", reinterpret_cast<LPVOID>(H_QueueNewlySpawned),
		reinterpret_cast<LPVOID*>(&_o_QueueNewlySpawned)},
	};''')

# перехватчики + флаг окна StartFrame
s = s.replace('''	void H_RunTickGroup(void* w, int group, bool block)''','''	// Окно StartFrame: нужно, чтобы сэмплер писал стеки только пока
	// диспетчер работает. Именно в этом окне спрятаны 40% времени кадра.
	std::atomic<int> g_in_startframe{0};
	std::atomic<uint64_t> g_sf_samples{0};
	std::atomic<uint64_t> g_sf_in_ntdll{0};

	void H_FillLevelList(void* self)
	{
		const uint64_t t0 = NowNs();
		_o_FillLevelList(self);
		AddSample(NowNs() - t0, g_phases[P_FillLevelList]);
	}

	void H_QueueAllTicks(void* self)
	{
		const uint64_t t0 = NowNs();
		_o_QueueAllTicks(self);
		AddSample(NowNs() - t0, g_phases[P_QueueAllTicks]);
	}

	void H_QueueNewlySpawned(void* self)
	{
		const uint64_t t0 = NowNs();
		_o_QueueNewlySpawned(self);
		AddSample(NowNs() - t0, g_phases[P_QueueNewlySpawned]);
	}

	void H_RunTickGroup(void* w, int group, bool block)''')

s = s.replace('''	void H_StartFrame(void* self, void* w, float dt, int tick_type)
	{
		const uint64_t t0 = NowNs();
		_o_StartFrame(self, w, dt, tick_type);
		AddSample(NowNs() - t0, g_phases[P_TickTaskStartFrame]);
	}''','''	void H_StartFrame(void* self, void* w, float dt, int tick_type)
	{
		const uint64_t t0 = NowNs();
		g_in_startframe.store(1, std::memory_order_relaxed);
		_o_StartFrame(self, w, dt, tick_type);
		g_in_startframe.store(0, std::memory_order_relaxed);
		AddSample(NowNs() - t0, g_phases[P_TickTaskStartFrame]);
	}''')

# объявления исходных функций
s = s.replace('''	void (*_o_CollectGarbage)(uint32_t, bool) = nullptr;''','''	void (*_o_CollectGarbage)(uint32_t, bool) = nullptr;
	void (*_o_FillLevelList)(void*) = nullptr;
	void (*_o_QueueAllTicks)(void*) = nullptr;
	void (*_o_QueueNewlySpawned)(void*) = nullptr;''')

io.open(p, "w", encoding="utf-8").write(s)
print("фазы добавлены")

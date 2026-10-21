import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(p, encoding="utf-8").read()

# ---- fncache: линейная проба + счётчики ----
old = '''		const size_t idx = h & 4095;
		FnCacheEntry* e = &g_fncache[idx];
		if (e->used && e->cls == self && e->name == name && e->super_flag == super_flag)
			return e->fn;

		void* v = _o_FindFunctionByName(self, name, super_flag);
		e->cls = self;
		e->name = name;
		e->super_flag = super_flag;
		e->fn = v;
		e->used = 1;
		return v;'''
new = '''		// Линейная проба на 8 слотов: однолотовый кэш при числе живых пар больше
		// размера таблицы вытеснял ключи и давал оверхед хука плюс промах.
		const size_t base_idx = h & 4095;
		FnCacheEntry* slot = nullptr;
		for (size_t i = 0; i < 8; ++i)
		{
			FnCacheEntry* e = &g_fncache[(base_idx + i) & 4095];
			if (e->used && e->cls == self && e->name == name && e->super_flag == super_flag)
			{
				g_fn_hit.fetch_add(1, std::memory_order_relaxed);
				return e->fn;
			}
			if (!e->used && !slot)
				slot = e;
		}
		g_fn_miss.fetch_add(1, std::memory_order_relaxed);
		void* v = _o_FindFunctionByName(self, name, super_flag);
		if (slot)
		{
			slot->cls = self;
			slot->name = name;
			slot->super_flag = super_flag;
			slot->fn = v;
			slot->used = 1;
		}
		return v;'''
assert old in s
s = s.replace(old, new)
s = s.replace('''	bool g_fncache_hook_installed = false;
	std::atomic<bool> g_fncache_on{false};''','''	bool g_fncache_hook_installed = false;
	std::atomic<bool> g_fncache_on{false};
	std::atomic<uint64_t> g_fn_hit{0};
	std::atomic<uint64_t> g_fn_miss{0};''')
s = s.replace('''		std::memset(g_fncache, 0, sizeof(g_fncache));
		g_fncache_on.store(on);
		LogLine(S("fncache: кэш {}", on ? "включён" : "выключен"));''','''		std::memset(g_fncache, 0, sizeof(g_fncache));
		g_fn_hit.store(0);
		g_fn_miss.store(0);
		g_fncache_on.store(on);
		LogLine(S("fncache: кэш {}", on ? "включён" : "выключен"));
		if (on)
			LogLine(S("fncache: счётчики попаданий/промахов обнулены"));''')

# ---- iscache: так же ----
old2 = '''		const size_t idx = h & 4095;
		IsChildEntry* e = &g_iscache[idx];
		if (e->used && e->child == self && e->parent == other)
			return e->result;
		const bool r = _o_IsChildOf(self, other);
		e->child = self;
		e->parent = other;
		e->result = r;
		e->used = true;
		return r;'''
new2 = '''		const size_t base_idx = h & 4095;
		IsChildEntry* slot = nullptr;
		for (size_t i = 0; i < 8; ++i)
		{
			IsChildEntry* e = &g_iscache[(base_idx + i) & 4095];
			if (e->used && e->child == self && e->parent == other)
			{
				g_is_hit.fetch_add(1, std::memory_order_relaxed);
				return e->result;
			}
			if (!e->used && !slot)
				slot = e;
		}
		g_is_miss.fetch_add(1, std::memory_order_relaxed);
		const bool r = _o_IsChildOf(self, other);
		if (slot)
		{
			slot->child = self;
			slot->parent = other;
			slot->result = r;
			slot->used = true;
		}
		return r;'''
assert old2 in s
s = s.replace(old2, new2)
s = s.replace('''	bool g_iscache_hook_installed = false;
	std::atomic<bool> g_iscache_on{false};''','''	bool g_iscache_hook_installed = false;
	std::atomic<bool> g_iscache_on{false};
	std::atomic<uint64_t> g_is_hit{0};
	std::atomic<uint64_t> g_is_miss{0};''')
s = s.replace('''		std::memset(g_iscache, 0, sizeof(g_iscache));
		g_iscache_on.store(on);
		LogLine(S("iscache: кэш {}", on ? "включён" : "выключен"));''','''		std::memset(g_iscache, 0, sizeof(g_iscache));
		g_is_hit.store(0);
		g_is_miss.store(0);
		g_iscache_on.store(on);
		LogLine(S("iscache: кэш {}", on ? "включён" : "выключен"));''')

# ---- команда отчёта по кэшам ----
s = s.replace('''	void CmdFnCache(RCONClientConnection*, RCONPacket* packet, UWorld*)''','''	void CmdCacheStat(RCONClientConnection*, RCONPacket*, UWorld*)
	{
		const uint64_t fh = g_fn_hit.load(), fm = g_fn_miss.load();
		const uint64_t ih = g_is_hit.load(), im = g_is_miss.load();
		LogLine(S("cachestat: fncache попаданий={} промахов={} ({:.1f}%)", fh, fm,
			100.0 * fh / (fh + fm ? fh + fm : 1)));
		LogLine(S("cachestat: iscache попаданий={} промахов={} ({:.1f}%)", ih, im,
			100.0 * ih / (ih + im ? ih + im : 1)));
	}

	void CmdFnCache(RCONClientConnection*, RCONPacket* packet, UWorld*)''')
s = s.replace('\tcmds.AddRconCommand("TickProf.tickq",',
 '\tcmds.AddRconCommand("TickProf.cachestat", [](RCONClientConnection*, RCONPacket*, UWorld*) { CmdCacheStat(); });\n'
 '\tcmds.AddRconCommand("TickProf.tickq",')
s = s.replace('"TickProf.tickoff", "TickProf.nochart", "TickProf.tickq", "TickProf.tickqreport",',
              '"TickProf.tickoff", "TickProf.nochart", "TickProf.cachestat",\n\t\t\t "TickProf.tickq", "TickProf.tickqreport",')
io.open(p, "w", encoding="utf-8").write(s)
print("ok")

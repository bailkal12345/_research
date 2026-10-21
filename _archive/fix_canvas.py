import io, re
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(p, encoding="utf-8").read()

start = s.index("\t// =========================================================================\n\t//  Кэш UCanvas по имени.")
end = s.index("\tvoid OnTickPerf(float /*dt*/)", start)
new_block = '''	// =========================================================================
	//  Кэш UCanvas по имени.
	//
	//  2.5% профиля GameThread уходит в TSet<FName,FFoliageMeshInfo*>::FindId,
	//  которую зовут DoGetCanvasByName / GetCanvasByName / FindFunctionByName —
	//  это поиск канвасов графа Kismet. На dedicated server канвасы не рисуются,
	//  но вызовы идут каждый кадр. Кэш сохраняет семантику: набор канвасов
	//  за сессию не меняется.
	// =========================================================================
	// Сигнатура из PDB: UCanvas* __cdecl DoGetCanvasByName(FName)
	void (*_o_DoGetCanvasByName)(uint64_t) = nullptr;
	void* g_canvas_cache[1024];
	uint64_t g_canvas_hash[1024];
	bool g_canvas_used[1024];
	bool g_canvas_hook_installed = false;
	std::atomic<bool> g_canvas_on{false};

	void* H_DoGetCanvasByName(uint64_t name)
	{
		if (!g_canvas_on.load(std::memory_order_relaxed))
			return _o_DoGetCanvasByName(name);

		uint64_t h = name * 1099511628211ULL;
		h ^= h >> 29;
		h |= 1;
		const size_t idx = h & 1023;
		if (g_canvas_used[idx] && g_canvas_hash[idx] == h)
			return g_canvas_cache[idx];

		void* v = _o_DoGetCanvasByName(name);
		if (!v)
		{
			// отрицательный результат тоже кэшируем: повторов много
			g_canvas_used[idx] = true;
			g_canvas_hash[idx] = h;
			g_canvas_cache[idx] = nullptr;
		}
		else
		{
			g_canvas_used[idx] = true;
			g_canvas_hash[idx] = h;
			g_canvas_cache[idx] = v;
		}
		return v;
	}

	void CmdCanvasCache(RCONClientConnection*, RCONPacket* packet, UWorld*)
	{
		const bool on = ArgInt(packet, 0) != 0;
		if (on && !g_canvas_hook_installed)
		{
			const bool ok = ArkApi::GetHooks().SetHook("Global.DoGetCanvasByName",
				reinterpret_cast<LPVOID>(H_DoGetCanvasByName),
				reinterpret_cast<LPVOID*>(&_o_DoGetCanvasByName));
			g_canvas_hook_installed = ok;
			LogLine(S("canvas: хук DoGetCanvasByName {}", ok ? "установлен" : "НЕ удался"));
			if (!ok)
				return;
		}
		std::memset(g_canvas_used, 0, sizeof(g_canvas_used));
		g_canvas_on.store(on);
		LogLine(S("canvas: кэш {}", on ? "включён" : "выключен"));
	}

'''
s = s[:start] + new_block + s[end:]
io.open(p, "w", encoding="utf-8").write(s)
print("ok")

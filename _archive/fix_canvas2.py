import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
lines = io.open(p, encoding="utf-8").read().split("\n")
# блок: с 1364 (1-based 1365) по строку перед void OnTickPerf
start = 1363  # 0-based индекс строки "// ====..." перед "//  Кэш UCanvas"
while start > 0 and "Кэш UCanvas" not in lines[start]:
    start -= 1
while start > 0 and "=====" not in lines[start]:
    start -= 1
end = start
while "void OnTickPerf" not in lines[end]:
    end += 1
new_block = '''	// =========================================================================
	//  Кэш UCanvas по имени.
	//
	//  2.5% профиля GameThread уходит в TSet<FName,FFoliageMeshInfo*>::FindId,
	//  которую зовут DoGetCanvasByName / GetCanvasByName / FindFunctionByName —
	//  это поиск канвасов графа Kismet. На dedicated server канвасы не рисуются,
	//  но вызовы идут каждый кадр. Набор канвасов за сессию не меняется,
	//  поэтому кэш сохраняет семантику.
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
		// отрицательный результат тоже кэшируем: повторов много
		g_canvas_used[idx] = true;
		g_canvas_hash[idx] = h;
		g_canvas_cache[idx] = v;
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
'''.split("\n")
out = lines[:start] + new_block + lines[end:]
io.open(p, "w", encoding="utf-8").write("\n".join(out))
print("replaced lines", start+1, "..", end)

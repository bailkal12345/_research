import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(p, encoding="utf-8").read()

# 1) спавн: параметры по умолчанию (прежние флаги ломали регистрацию актора)
old = """		FActorSpawnParameters params;
		params.bNoFail = true;
		params.bNoCollisionFail = true;
		params.ObjectFlags = EObjectFlags::RF_Transient;

		std::lock_guard<std::mutex> lock(g_spawn_mutex);
		int32_t made = 0;
		for (int32_t i = 0; i < count; ++i)
		{
			const double ang = i * 2.39996323;
			const float r = 300.0f + (i % 40) * 50.0f;
			FVector pos = origin + FVector(static_cast<float>(r * cos(ang)), static_cast<float>(r * sin(ang)), 200.0f);"""
new = """		// параметры по умолчанию: прежние bNoFail/RF_Transient роняли регистрацию
		FActorSpawnParameters params;

		std::lock_guard<std::mutex> lock(g_spawn_mutex);
		int32_t made = 0;
		for (int32_t i = 0; i < count; ++i)
		{
			const double ang = i * 2.39996323;
			const float r = 300.0f + (i % 40) * 50.0f;
			FVector pos = origin + FVector(static_cast<float>(r * cos(ang)), static_cast<float>(r * sin(ang)), 200.0f);"""
assert old in s
s = s.replace(old, new)

# 2) кэш UCanvas по имени: на dedicated server рисование не нужно,
#    но Kismet-вызовы GetCanvasByName идут постоянно (2.5% профиля).
cache = '''
// =========================================================================
//  Кэш UCanvas по имени.
//
//  По профилю 2.5% GameThread уходит в TSet<FName,FFoliageMeshInfo*>::FindId,
//  которую зовут GetCanvasByName / DoGetCanvasByName / FindFunctionByName:
//  это поиск канвасов Kismet-графа. На dedicated server канвасы не рисуются,
//  но вызовы идут каждый кадр. Кэш сохраняет семантику (объекты не меняются).
// =========================================================================
	struct CanvasCache
	{
		void* canvas[1024];
		uint64_t hash[1024];
		bool used[1024];
	};
	CanvasCache g_canvas;
	std::atomic<bool> g_canvas_cache_on{false};
	void (*_o_GetCanvasByName)(void*, void*, void*) = nullptr;
	bool g_canvas_hook_installed = false;

	uint64_t NameHash(const void* name)
	{
		// FName: ComparisonIndex + Number, достаточно первых двух полей
		uint64_t h = 1469598103934665603ULL;
		const auto* p = static_cast<const uint64_t*>(name);
		for (int i = 0; i < 2; ++i)
		{
			h ^= p[i];
			h *= 1099511628211ULL;
		}
		return h | 1;
	}

	void H_GetCanvasByName(void* self, void* name, void* result)
	{
		if (g_canvas_cache_on)
		{
			const uint64_t h = NameHash(name);
			const size_t idx = h & 1023;
			if (g_canvas.used[idx] && g_canvas.hash[idx] == h)
			{
				*reinterpret_cast<void**>(result) = g_canvas.canvas[idx];
				return;
			}
			_o_GetCanvasByName(self, name, result);
			void* v = *reinterpret_cast<void**>(result);
			if (!v)
			{
				v = const_cast<void*>(static_cast<const void*>(this));
				g_canvas.used[idx] = true;
				g_canvas.hash[idx] = h;
				g_canvas.canvas[idx] = v;
			}
			return;
		}
		_o_GetCanvasByName(self, name, result);
	}

	void CmdCanvasCache(RCONClientConnection*, RCONPacket* packet, UWorld*)
	{
		const bool on = ArgInt(packet, 0) != 0;
		if (on && !g_canvas_hook_installed)
		{
			const bool ok = ArkApi::GetHooks().SetHook("UCanvas.GetCanvasByName",
				reinterpret_cast<LPVOID>(H_GetCanvasByName), reinterpret_cast<LPVOID*>(&_o_GetCanvasByName));
			g_canvas_hook_installed = ok;
			LogLine(S("canvas: хук GetCanvasByName {}", ok ? "установлен" : "НЕ удался"));
			if (!ok)
				return;
		}
		std::memset(&g_canvas, 0, sizeof(g_canvas));
		g_canvas_cache_on.store(on);
		LogLine(S("canvas: кэш {}", on ? "включён" : "выключен"));
	}

	void OnTickPerf(float /*dt*/)'''
s = s.replace("	void OnTickPerf(float /*dt*/)", cache, 1)
s = s.replace('cmds.AddRconCommand("TickProf.overlaps", CmdOverlaps);',
              'cmds.AddRconCommand("TickProf.overlaps", CmdOverlaps);\n\tcmds.AddRconCommand("TickProf.cachename", CmdCanvasCache);')
io.open(p, "w", encoding="utf-8").write(s)
print("ok")

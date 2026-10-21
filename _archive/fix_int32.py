import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(p, encoding="utf-8").read()

# --- исправление: поле int32, а не float ---
s = s.replace('''	// UNetDriver::NetServerMaxTickRate (float, PDB offset 72) — единственный''',
'''	// UNetDriver::NetServerMaxTickRate — единственный''')
old = '''		auto* slot = reinterpret_cast<float*>(reinterpret_cast<char*>(drv) + NETDRIVER_MAXTICKRATE);
		const float old = *slot;
		const int32_t requested = ArgInt(packet, 30);
		// 0 — вернуть штатное ограничение сервера
		const float value = requested <= 0 ? 0.0f : static_cast<float>(requested);
		*slot = value;
		g_maxtickrate.store(value);

		// проверка: значение могло быть перезаписано конфигом при реините драйвера
		const float back = *slot;
		LogLine(S("maxfps: NetServerMaxTickRate {} -> {} (проверка {})", old, back, back == value ? "ок" : "НЕ ПРИМЕНИЛОСЬ"));'''
new = '''		// Поле int32 (декомпил: MOV EDX,[RAX+0x48]; CMP EDX,0xa; CMOVL — целочисленный
		// кламп, затем CVTDQ2PS). Раньше сюда писался float, и его биты читались
		// как огромное целое — инструмент «работал», но показывал чушь.
		auto* slot = reinterpret_cast<int32_t*>(reinterpret_cast<char*>(drv) + NETDRIVER_MAXTICKRATE);
		const int32_t old = *slot;
		const int32_t requested = ArgInt(packet, 30);
		// 0 — вернуть штатное ограничение сервера
		const int32_t value = requested <= 0 ? 0 : requested;
		*slot = value;
		g_maxtickrate.store(static_cast<float>(value));

		const int32_t back = *slot;
		LogLine(S("maxfps: NetServerMaxTickRate {} -> {} (проверка {})", old, back,
			back == value ? "ок" : "НЕ ПРИМЕНИЛОСЬ"));'''
assert old in s
s = s.replace(old, new)
s = s.replace('''		*reinterpret_cast<float*>(reinterpret_cast<char*>(drv) + NETDRIVER_MAXTICKRATE) = want;''',
              '''		*reinterpret_cast<int32_t*>(reinterpret_cast<char*>(drv) + NETDRIVER_MAXTICKRATE) =
			static_cast<int32_t>(want);''')

# --- П12: автоприменение патча зажима при старте ---
s = s.replace('''	constexpr uint8_t CLAMP_NEW[4] = {0xA0, 0x86, 0x01, 0x00}; // 100000''',
'''	constexpr uint8_t CLAMP_NEW[4] = {0xA0, 0x86, 0x01, 0x00}; // 100000
	std::atomic<int> g_clamp_autostart{0}; // 1 = поднять при загрузке плагина''')
s = s.replace('''	void CmdFixClamp(RCONClientConnection*, RCONPacket* packet, UWorld*)
	{
		PatchTickClamp(ArgInt(packet, 0) != 0);
	}''','''	void CmdFixClamp(RCONClientConnection*, RCONPacket* packet, UWorld*)
	{
		PatchTickClamp(ArgInt(packet, 0) != 0);
	}

	// П12: патч живёт только в памяти процесса, поэтому по умолчанию
	// поднимаем зажим сразу при загрузке плагина. Отключается файлом
	// tickprof_noclamp.txt рядом с плагином или командой fixclamp 0.
	void ApplyClampAutoStart()
	{
		FILE* f = nullptr;
		const std::string off = PluginDir() + "\\\\tickprof_noclamp.txt";
		if (fopen_s(&f, off.c_str(), "rb") == 0 && f)
		{
			fclose(f);
			LogLine(S("tickclamp: есть tickprof_noclamp.txt, авто-патч выключен"));
			return;
		}
		// лог ещё может быть недоступен на ранней стадии — пишем после загрузки мира
		g_clamp_autostart.store(1);
	}''')
s = s.replace('''		if (g_maxtickrate.load() > 0.0f && now_ms - last_maxfps_tick > 5000)''',
'''		if (g_clamp_autostart.exchange(0) != 0)
		{
			PatchTickClamp(true);
		}
		if (g_maxtickrate.load() > 0.0f && now_ms - last_maxfps_tick > 5000)''')
s = s.replace('''	LogLine(S("loaded (Plugin_Init)", PLUGIN_NAME));''',
'''	LogLine(S("loaded (Plugin_Init)", PLUGIN_NAME));
	ApplyClampAutoStart();''')
io.open(p, "w", encoding="utf-8").write(s)
print("ok")

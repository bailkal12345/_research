import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(p, encoding="utf-8").read()
# регистрация команды
s = s.replace('\tcmds.AddRconCommand("TickProf.count",',
 '\tcmds.AddRconCommand("TickProf.maxfps", [](RCONClientConnection* c, RCONPacket* p, UWorld* w) { CmdMaxTickRate(c, p, w); });\n'
 '\tcmds.AddRconCommand("TickProf.count",')
s = s.replace('"TickProf.fncache", "TickProf.overlapall", "TickProf.iscache"})',
              '"TickProf.fncache", "TickProf.overlapall", "TickProf.iscache", "TickProf.maxfps"})')
# переустановка значения раз в несколько секунд (драйвер может переинициализироваться)
s = s.replace('''		OnTickPerf();
		g_frames.fetch_add(1, std::memory_order_relaxed);''','''		OnTickPerf();
		g_frames.fetch_add(1, std::memory_order_relaxed);

		// значение лимита может сброситься при переинициализации драйвера
		static uint64_t last_maxfps_tick = 0;
		const uint64_t now_ms = GetTickCount64();
		if (g_maxtickrate.load() > 0.0f && now_ms - last_maxfps_tick > 5000)
		{
			last_maxfps_tick = now_ms;
			ApplyMaxTickRate();
		}''')
io.open(p, "w", encoding="utf-8").write(s)
print("ok")

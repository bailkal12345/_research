import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(p, encoding="utf-8").read()
# учёт задач за кадр в OnTick
s = s.replace('''		OnTickPerf();
		g_frames.fetch_add(1, std::memory_order_relaxed);''','''		OnTickPerf();
		g_frames.fetch_add(1, std::memory_order_relaxed);

		// сколько тик-задач было поставлено в очередь за прошедший кадр
		if (g_q_active.load(std::memory_order_relaxed))
		{
			const uint64_t n = g_frame_queued.exchange(0, std::memory_order_relaxed);
			g_q_sum.fetch_add(n, std::memory_order_relaxed);
			g_q_frames.fetch_add(1, std::memory_order_relaxed);
			const uint64_t mn = g_q_min.load(std::memory_order_relaxed);
			if (mn == 0 || n < mn)
				g_q_min.store(n, std::memory_order_relaxed);
			const uint64_t mx = g_q_max.load(std::memory_order_relaxed);
			if (n > mx)
				g_q_max.store(n, std::memory_order_relaxed);
		}''')
# регистрация команд
s = s.replace('\tcmds.AddRconCommand("TickProf.nochart",',
 '\tcmds.AddRconCommand("TickProf.tickq", [](RCONClientConnection* c, RCONPacket* p, UWorld* w) { CmdTickQueue(c, p, w); });\n'
 '\tcmds.AddRconCommand("TickProf.tickqreport", [](RCONClientConnection* c, RCONPacket* p, UWorld* w) { CmdTickQueueReport(c, p, w); });\n'
 '\tcmds.AddRconCommand("TickProf.actortickoff", [](RCONClientConnection* c, RCONPacket* p, UWorld* w) { CmdActorTickOff(c, p, w); });\n'
 '\tcmds.AddRconCommand("TickProf.nochart",')
s = s.replace('"TickProf.tickoff", "TickProf.nochart"})',
              '"TickProf.tickoff", "TickProf.nochart", "TickProf.tickq", "TickProf.tickqreport",\n\t\t\t "TickProf.actortickoff"})')
io.open(p, "w", encoding="utf-8").write(s)
print("ok")

import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(p, encoding="utf-8").read()
s = s.replace('\tcmds.AddRconCommand("TickProf.count",',
 '\tcmds.AddRconCommand("TickProf.cull", [](RCONClientConnection* c, RCONPacket* p, UWorld* w) { CmdCull(c, p, w); });\n'
 '\tcmds.AddRconCommand("TickProf.cullstat", [](RCONClientConnection*, RCONPacket*, UWorld*) {\n'
 '\t\tLogLine(S("cull: пропущено тиков {}", g_cull_skipped.load()));\n'
 '\t});\n'
 '\tcmds.AddRconCommand("TickProf.count",')
s = s.replace('"TickProf.iscache", "TickProf.maxfps"})',
              '"TickProf.iscache", "TickProf.maxfps", "TickProf.cull", "TickProf.cullstat"})')
# обновлять список игроков в тике
s = s.replace('''		// значение лимита может сброситься при переинициализации драйвера''',
'''		// список позиций игроков для отсечения тиков обновляем редко
		if (g_cull_on.load() && (g_frames.load() % 30) == 0)
		{
			RefreshPlayerPoints();
		}

		// значение лимита может сброситься при переинициализации драйвера''')
io.open(p, "w", encoding="utf-8").write(s)
print("ok")

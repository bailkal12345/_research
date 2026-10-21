import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
src = io.open(p, encoding="utf-8").read()
dup = """	void OnTick(float /*dt*/)
	{
		// вызывается на GameThread — запоминаем его tid
		if (g_game_tid.load() == 0)
		{
			g_game_tid.store(::GetCurrentThreadId());
			LogLine(S("game thread tid={}", PLUGIN_NAME, g_game_tid.load()));
		}
	}

"""
if dup in src:
    src = src.replace(dup, "", 1)
    io.open(p, "w", encoding="utf-8").write(src)
    print("removed duplicate OnTick")
else:
    print("pattern not found; occurrences of OnTick:", src.count("void OnTick"))

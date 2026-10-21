import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(p, encoding="utf-8").read()
# убрать позднее объявление
s = s.replace('''	std::atomic<int> g_clamp_autostart{0}; // 1 = поднять при загрузке плагина
''', '')
# объявить рядом с прочими ранними
s = s.replace('''	constexpr const char* PLUGIN_NAME = "TickProf";''',
'''	constexpr const char* PLUGIN_NAME = "TickProf";

	// П12: отложенное применение патча зажима тикрейта (см. ApplyClampAutoStart)
	std::atomic<int> g_clamp_autostart{0};''')
io.open(p, "w", encoding="utf-8").write(s)
print("ok")

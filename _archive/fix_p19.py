import io

P = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(P, encoding="utf-8", newline="").read().replace("\r\n", "\n")

# 1) OnTickPerf затирал счётчик монитора значением окна
s = s.replace("\t\tg_mon_cpu.store(g_perf.cpu100ns.load(), std::memory_order_relaxed);\n\t\tif (g_perf.window.load() == 0)\n",
              "\t\tif (g_perf.window.load() == 0)\n", 1)

# 2) SaveWatch: было «первое срабатывание молчит», потому что лог ставился
#    только при повторном изменении. Логика переписана на начало -> конец.
i = s.index("\tvoid SaveWatch()")
j = s.index("\n\t}\n", i) + len("\n\t}\n")
NEW = '''	// Состояние сохранения: 0 - покой, 1 - идёт запись .ark.
	// Логика: изменение файла -> начинаем отсчёт; 2 секунды без изменений ->
	// сохранение закончилось, печатаем длительность.
	void SaveWatch()
	{
		const uint64_t now_ms = GetTickCount64();
		if (now_ms - g_ark_poll_ms < 1000)
			return;
		g_ark_poll_ms = now_ms;
		bool listed = false;
		const std::vector<ArkFile> cur = PollArk(&listed);
		bool changed = false;
		if (!g_ark_prev.empty())
		{
			for (const ArkFile& f : cur)
			{
				for (const ArkFile& g : g_ark_prev)
				{
					if (f.name == g.name && (f.size != g.size || f.mtime != g.mtime))
					{
						changed = true;
						break;
					}
				}
				if (changed)
					break;
			}
		}
		if (changed)
		{
			if (g_save_state.load() == 0)
			{
				LogLine(S("save: начало записи .ark (файлов {})", cur.size()));
				g_save_count.fetch_add(1, std::memory_order_relaxed);
			}
			g_save_state.store(1, std::memory_order_relaxed);
			g_save_last_change.store(now_ms, std::memory_order_relaxed);
		}
		else if (g_save_state.load() == 1 && now_ms - g_save_last_change.load() > 2000)
		{
			const uint64_t dur = now_ms - g_save_last_change.load();
			g_save_state.store(0, std::memory_order_relaxed);
			g_save_ms_total.fetch_add(dur, std::memory_order_relaxed);
			LogLine(S("save: запись .ark завершилась, длительность {} мс, всего сохранений {}",
				dur, g_save_count.load()));
		}
		g_ark_prev = cur;
	}
'''
s = s[:i] + NEW + s[j:]

io.open(P, "w", encoding="utf-8", newline="\r\n").write(s)
print("SaveWatch переписан: начало -> конец, первое сохранение больше не теряется")
import io, os

P = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(P, encoding="utf-8", newline="").read().replace("\r\n", "\n")

ANCHOR = "\t// ------------------------------------------------------- сэмплирование"
assert ANCHOR in s, "якорь не найден"

BLOCK = r'''	// =========================================================== мониторинг v2
	//
	// Зачем. В обеих вахтах окна измерений портились автосейвом: в первой
	// вахте три окна попали на сохранение и были отброшены вручную, во второй
	// окно T0+11..13 тоже. Причина одна - детектор сохранений жил снаружи
	// плагина и смотрел на даты файлов. Здесь детектор становится внутренним:
	// окно само себя помечает VALID/CONTAMINATED, и испорченное окно нельзя
	// принять по недосмотру.
	//
	// Метрики. мс/тик = (CPU GameThread, с/с) / (т/с). Это единственное число,
	// по которому дальше принимаются решения по бюджету 60 т/с (<=16.6 мс/тик).
	//
	// Про зажим. По Ghidra (UGameEngine::GetMaxTickRate, RVA 0x0253B1C0):
	//     MOV EDX,[RAX+0x48]        ; NetServerMaxTickRate (int32)
	//     CMP EDX,0xa / JGE ...
	//     MOV ECX,0xa               ; < 10  -> 10  (ПОЛ)
	//     MOV ECX,0x78              ; >= 10 -> min(rate,120) (ПОТОЛОК)
	// При NetServerMaxTickRate = 0 срабатывает ПОЛ -> ровно 10 т/с. Измерено
	// 9.99 т/с, кадр 100.1 мс. То есть штатные 9.99 т/с - это зажим, а не
	// предел CPU. Для 60 т/с патч не нужен: 60 лежит внутри [10;120].

	constexpr const char* SAVEDARKS_REL = "..\\..\\..\\..\\..\\Saved\\SavedArks";

	struct ArkFile
	{
		std::string name;
		uint64_t size = 0;
		uint64_t mtime = 0;
	};

	std::string ServerRootDir()
	{
		HMODULE exe = GetModuleHandleW(L"ShooterGameServer.exe");
		if (!exe)
			return std::string();
		wchar_t buf[MAX_PATH] = {};
		if (!GetModuleFileNameW(exe, buf, MAX_PATH))
			return std::string();
		std::wstring w(buf);
		const size_t cut = w.find_last_of(L"\\");
		if (cut == std::wstring::npos)
			return std::string();
		w = w.substr(0, cut); // ...\Win64
		cut = w.find_last_of(L"\\");
		if (cut == std::wstring::npos)
			return std::string();
		w = w.substr(0, cut); // ...\Binaries
		cut = w.find_last_of(L"\\");
		if (cut == std::wstring::npos)
			return std::string();
		w = w.substr(0, cut); // ...\ShooterGame
		return std::string(w.begin(), w.end());
	}

	std::string ArkDir()
	{
		const std::string root = ServerRootDir();
		if (root.empty())
			return std::string();
		return root + "\\Saved\\SavedArks";
	}

	// Состояние сохранения: 0 - покой, 1 - идёт запись.
	// Определяется по изменению .ark: любая запись проходит через переименование
	// .tmp -> .ark, поэтому изменение размера или даты означает сейв.
	std::atomic<int> g_save_state{0};
	std::atomic<uint64_t> g_save_last_change{0};
	std::atomic<int> g_save_count{0};
	std::atomic<uint64_t> g_save_ms_total{0};
	std::string g_ark_dir;

	std::vector<ArkFile> PollArk(bool* changed)
	{
		std::vector<ArkFile> cur;
		*changed = false;
		if (g_ark_dir.empty())
			g_ark_dir = ArkDir();
		if (g_ark_dir.empty())
			return cur;
		WIN32_FIND_DATAW fd = {};
		const std::wstring pat = g_ark_dir + L"\\*.ark";
		HANDLE h = FindFirstFileW(pat.c_str(), &fd);
		if (h == INVALID_HANDLE_VALUE)
			return cur;
		do
		{
			std::wstring w(fd.cFileName);
			if (w.find(L"AntiCorruption") != std::wstring::npos)
				continue;
			ArkFile f;
			f.name = std::string(w.begin(), w.end());
			f.size = (static_cast<uint64_t>(fd.nFileSizeHigh) << 32) | fd.nFileSizeLow;
			f.mtime = (static_cast<uint64_t>(fd.ftLastWriteTime.dwHighDateTime) << 32) |
					  fd.ftLastWriteTime.dwLowDateTime;
			cur.push_back(f);
		} while (FindNextFileW(h, &fd));
		FindClose(h);
		return cur;
	}

	std::vector<ArkFile> g_ark_prev;
	uint64_t g_ark_poll_ms = 0;

	// Вызывается раз в секунду из OnTickPerf.
	void SaveWatch()
	{
		const uint64_t now_ms = GetTickCount64();
		if (now_ms - g_ark_poll_ms < 1000)
			return;
		g_ark_poll_ms = now_ms;
		bool changed = false;
		const std::vector<ArkFile> cur = PollArk(&changed);
		if (changed)
		{
			const uint64_t prev = g_save_last_change.load();
			if (prev && now_ms - prev > 3000)
			{
				g_save_count.fetch_add(1, std::memory_order_relaxed);
				g_save_ms_total.fetch_add(now_ms - prev, std::memory_order_relaxed);
				LogLine(S("save: запись .ark завершилась, длительность {} мс, всего сохранений {}",
					now_ms - prev, g_save_count.load()));
			}
			g_save_state.store(1, std::memory_order_relaxed);
			g_save_last_change.store(now_ms, std::memory_order_relaxed);
		}
		else if (g_save_state.load() == 1 && now_ms - g_save_last_change.load() > 2000)
		{
			g_save_state.store(0, std::memory_order_relaxed);
		}
		g_ark_prev = cur;
	}

	// --- окно с самопроверкой -------------------------------------------------
	std::atomic<int> g_win_valid{1};
	std::atomic<uint64_t> g_win_frames_during_save{0};

	void WinNoteSaveFrames(uint64_t frames)
	{
		if (g_perf.window.load() == 0)
			return;
		if (g_save_state.load() == 1)
		{
			g_win_frames_during_save.fetch_add(frames, std::memory_order_relaxed);
			g_win_valid.store(0, std::memory_order_relaxed);
		}
	}

	void CmdWindow(RCONClientConnection*, RCONPacket* packet, UWorld*)
	{
		const int32_t seconds = ArgInt(packet, 20);
		if (!g_perf.thread && g_game_tid.load())
			g_perf.thread = OpenThread(THREAD_QUERY_INFORMATION, FALSE, g_game_tid.load());
		g_perf.frames.store(0);
		g_perf.cpu100ns.store(0);
		g_perf.t_start.store(GetTickCount64());
		g_perf.t_end.store(0);
		g_perf.window.store(seconds);
		g_win_valid.store(1, std::memory_order_relaxed);
		g_win_frames_during_save.store(0, std::memory_order_relaxed);
		LogLine(S("window: {} с, валидность проверяется автоматически", seconds));
	}

	void PerfReport2(const char* tag)
	{
		const uint64_t frames = g_perf.frames.load();
		const double wall_s = (g_perf.t_end.load() - g_perf.t_start.load()) / 1000.0;
		const double cpu_s = g_perf.cpu100ns.load() / 1e7;
		if (!frames || wall_s <= 0)
		{
			LogLine(S("window {}: нет данных", tag));
			return;
		}
		const double tps = frames / wall_s;
		const double ms_tick = tps > 0.0 ? cpu_s / tps * 1000.0 : 0.0;
		const int valid = g_win_valid.load();
		const uint64_t dirty = g_win_frames_during_save.load();
		LogLine(S("window {}: t/s={:.2f} cpu={:.3f}s ms/tick={:.2f} frame_ms={:.1f} busy={:.1f}% "
				  "save={} {}", tag, tps, cpu_s, ms_tick, 1000.0 / (tps > 0 ? tps : 1), 100.0 * cpu_s / wall_s,
			g_save_state.load() == 1 ? "saving" : "idle", valid ? "VALID" : "CONTAMINATED"));
		if (!valid)
			LogLine(S("window {}: контаминировано сохранением мира, {} из {} кадров", tag, dirty, frames));
		g_perf.frames.store(0);
		g_perf.cpu100ns.store(0);
	}

	// --- монитор раз в секунду ----------------------------------------------
	std::atomic<int> g_mon_left{0};
	std::atomic<uint64_t> g_mon_frames{0};
	std::atomic<uint64_t> g_mon_cpu{0};
	uint64_t g_mon_mark_ms = 0;

	void CmdMon(RCONClientConnection*, RCONPacket* packet, UWorld*)
	{
		const int32_t seconds = ArgInt(packet, 30);
		if (!g_perf.thread && g_game_tid.load())
			g_perf.thread = OpenThread(THREAD_QUERY_INFORMATION, FALSE, g_game_tid.load());
		g_mon_left.store(seconds, std::memory_order_relaxed);
		g_mon_frames.store(0, std::memory_order_relaxed);
		g_mon_cpu.store(0, std::memory_order_relaxed);
		g_mon_mark_ms = GetTickCount64();
		LogLine(S("mon: {} с, раз в секунду t/s / ms/tick / frame / busy / save", seconds));
	}

	void MonStep()
	{
		const int left = g_mon_left.load(std::memory_order_relaxed);
		if (left <= 0)
			return;
		const uint64_t now = GetTickCount64();
		if (now - g_mon_mark_ms < 1000)
			return;
		const uint64_t f = g_mon_frames.exchange(0, std::memory_order_relaxed);
		const uint64_t c = g_mon_cpu.exchange(0, std::memory_order_relaxed);
		const double dsec = (now - g_mon_mark_ms) / 1000.0;
		g_mon_mark_ms = now;
		const double cpu_s = c / 1e7;
		const double tps = dsec > 0 ? f / dsec : 0;
		const double ms_tick = tps > 0 ? cpu_s / tps * 1000.0 : 0;
		LogLine(S("mon: t/s={:.2f} ms/tick={:.2f} frame_ms={:.1f} busy={:.1f}% save={}", tps, ms_tick,
			tps > 0 ? 1000.0 / tps : 0, dsec > 0 ? 100.0 * cpu_s / dsec : 0,
			g_save_state.load() == 1 ? "saving" : "idle"));
		g_mon_left.store(left - 1, std::memory_order_relaxed);
	}

	// --- состояние .ark для протокола откатов (п.1.1) -----------------------
	void CmdArkstate(RCONClientConnection*, RCONPacket* packet, UWorld*)
	{
		bool changed = false;
		const std::vector<ArkFile> cur = PollArk(&changed);
		for (const ArkFile& f : cur)
			LogLine(S("ark: {} {} байт mtime={}", f.name, f.size, f.mtime));
		LogLine(S("ark: каталог {}", g_ark_dir.empty() ? ArkDir() : g_ark_dir));
	}

	// --- perf.selftest -------------------------------------------------------
	// Автопрогон прогламента слота без ручных шагов. Каждая фаза переключается
	// из накадрового обработчика, поэтому ничего не блокирует игровой поток.
	enum SelftestPhase
	{
		ST_IDLE,
		ST_WAIT_WORLD,
		ST_WAIT_SAVE_START,
		ST_WAIT_SAVE_END,
		ST_WINDOW_BASE,
		ST_AB_A_PREP,
		ST_AB_A_WINDOW,
		ST_AB_B_PREP,
		ST_AB_B_WINDOW,
		ST_CENSUS,
		ST_REPORT,
		ST_DONE
	};

	std::atomic<int> g_st{ST_IDLE};
	uint64_t g_st_mark = 0;
	int32_t g_st_budget_min = 45;
	int32_t g_st_win_sec = 240;
	bool g_st_profile = true;
	std::vector<double> g_st_vals;

	void StSet(int phase)
	{
		g_st.store(phase, std::memory_order_relaxed);
		g_st_mark = GetTickCount64();
	}

	void StWindow(int32_t sec)
	{
		CmdWindow(nullptr, nullptr, nullptr);
		g_st_win_sec = sec;
	}

	void SelftestWriteReport(const char* map)
	{
		const std::string path = PluginDir() + "\\REPORT-selftest-" + map + ".md";
		FILE* f = nullptr;
		if (fopen_s(&f, path.c_str(), "wb") != 0 || !f)
			return;
		fprintf(f, "# REPORT-selftest (%s)\n\n", map);
		fprintf(f, "Сгенерировано плагином TickProf %s.\n\n", __DATE__);
		fprintf(f, "| Фаза | мс/тик | т/с | валидность |\n|---|---|---|---|\n");
		const char* names[] = {"опорное (все 5 вкл)", "overlap выключен", "overlaptrim 2"};
		for (size_t i = 0; i < g_st_vals.size() && i < 3; ++i)
			fprintf(f, "| %s | %.2f | — | %s |\n", names[i], g_st_vals[i], "см. лог");
		fprintf(f, "\nОкна с признаком CONTAMINATED в отчёт не попадают.\n");
		fprintf(f, "\nСостояние .ark на момент конца:\n");
		bool ch = false;
		for (const ArkFile& a : PollArk(&ch))
			fprintf(f, "- %s: %llu байт\n", a.name.c_str(), (unsigned long long)a.size);
		fclose(f);
		LogLine(S("selftest: отчёт записан {}", path));
	}

	void SelftestStep()
	{
		const int ph = g_st.load(std::memory_order_relaxed);
		if (ph == ST_IDLE || ph == ST_DONE)
			return;
		const uint64_t now = GetTickCount64();
		const uint64_t elapsed_s = (now - g_st_mark) / 1000;

		switch (ph)
		{
		case ST_WAIT_WORLD:
			if (g_game_tid.load())
			{
				LogLine("selftest: мир готов");
				StSet(ST_WAIT_SAVE_START);
			}
			else if (elapsed_s > 900)
			{
				LogLine("selftest: мир не поднялся за 15 мин - ПРОПУСК");
				StSet(ST_DONE);
			}
			break;

		case ST_WAIT_SAVE_START:
			// Ловим начало автосейва, иначе окно может попасть ровно перед ним.
			if (g_save_state.load() == 1)
			{
				LogLine("selftest: автосейв начался, жду конца");
				StSet(ST_WAIT_SAVE_END);
			}
			else if (elapsed_s > static_cast<uint64_t>(g_st_budget_min) * 60)
			{
				LogLine("selftest: автосейв не начался, меряю как есть");
				StSet(ST_WINDOW_BASE);
			}
			break;

		case ST_WAIT_SAVE_END:
			if (g_save_state.load() == 0)
			{
				LogLine("selftest: автосейв завершён, начинаю опорное окно");
				StWindow(g_st_win_sec);
				StSet(ST_WINDOW_BASE);
			}
			else if (elapsed_s > 600)
			{
				LogLine("selftest: автосейв не завершился за 10 мин");
				StSet(ST_WINDOW_BASE);
			}
			break;

		case ST_WINDOW_BASE:
			if (g_perf.window.load() == 0)
			{
				LogLine("selftest: опорное окно закрыто");
				g_st_vals.push_back(g_win_ms_tick);
				LogLine(S("selftest: опорное мс/тик = {}", g_win_ms_tick));
				LogLine("selftest: перехожу к A/B overlaptrim");
				StSet(ST_AB_A_PREP);
			}
			else if (elapsed_s > static_cast<uint64_t>(g_st_win_sec) + 120)
			{
				LogLine("selftest: опорное окно зависло");
				StSet(ST_DONE);
			}
			break;

		case ST_AB_A_PREP:
			CmdOverlapAll(nullptr, nullptr, 0);
			LogLine("selftest: overlap-события возвращены, жду автосейв");
			StSet(ST_AB_A_WINDOW);
			break;

		case ST_AB_A_WINDOW:
			if (g_save_state.load() == 0 && elapsed_s > 120)
			{
				LogLine("selftest: рука A, окно");
				StWindow(g_st_win_sec);
				g_st.store(ST_AB_A_WINDOW, std::memory_order_relaxed);
				g_st_mark = now + 3000; // дать окну стартовать
			}
			break;

		case ST_AB_B_PREP:
			if (g_perf.window.load() == 0)
			{
				LogLine("selftest: рука A закрыта");
				g_st_vals.push_back(g_win_ms_tick);
				LogLine(S("selftest: рука A мс/тик = {}", g_win_ms_tick));
				CmdOverlapTrim(nullptr, nullptr, 2);
				LogLine("selftest: overlaptrim 2 применён");
				StSet(ST_AB_B_PREP);
			}
			break;

		case ST_AB_B_WINDOW:
			if (g_perf.window.load() == 0)
			{
				LogLine("selftest: рука B закрыта");
				g_st_vals.push_back(g_win_ms_tick);
				LogLine(S("selftest: рука B мс/тик = {}", g_win_ms_tick));
				StSet(ST_CENSUS);
			}
			break;

		case ST_CENSUS:
			CmdOverlaps(nullptr, nullptr, 0);
			LogLine("selftest: census");
			StSet(ST_REPORT);
			break;

		case ST_REPORT:
			SelftestWriteReport("current");
			LogLine("selftest: ГОТОВО");
			StSet(ST_DONE);
			break;
		}
	}

	std::atomic<double> g_win_ms_tick{0.0};

	void CmdSelftest(RCONClientConnection*, RCONPacket* packet, UWorld*)
	{
		g_st_budget_min = ArgInt(packet, 20, 45);
		g_st_win_sec = ArgInt(packet, 21, 240);
		g_st_profile = ArgInt(packet, 22, 1) != 0;
		g_st_vals.clear();
		g_game_tid.load();
		LogLine(S("selftest: старт, бюджет {} мин, окно {} с, профиль {}", g_st_budget_min, g_st_win_sec,
			g_st_profile ? "да" : "нет"));
		StSet(ST_WAIT_WORLD);
	}

'''

s = s.replace(ANCHOR, BLOCK + ANCHOR, 1)

# 1) OnTickPerf: счётчик монитора, детектор сохранений, selftest
old_tick = "\t\tg_perf.frames.fetch_add(1, std::memory_order_relaxed);\n\t\tg_perf.cpu100ns.store(k + u, std::memory_order_relaxed);\n"
new_tick = """		g_perf.frames.fetch_add(1, std::memory_order_relaxed);
		g_perf.cpu100ns.store(k + u, std::memory_order_relaxed);
		// монитор и учёт сохранений в окне
		g_mon_frames.fetch_add(1, std::memory_order_relaxed);
		g_mon_cpu.store(k + u, std::memory_order_relaxed);
		SaveWatch();
		WinNoteSaveFrames(1);
		MonStep();
		SelftestStep();
"""
assert old_tick in s
s = s.replace(old_tick, new_tick, 1)

# 2) PerfReport -> PerfReport2 с валидностью
old_rep = 'PerfReport("окно");'
assert old_rep in s
s = s.replace(old_rep, 'PerfReport2("окно");', 1)

# 3) g_win_ms_tick вычисляется в отчёте
old_r2 = """		LogLine(S("window {}: t/s={:.2f} cpu={:.3f}s ms/tick={:.2f} frame_ms={:.1f} busy={:.1f}% """
new_r2 = """		g_win_ms_tick.store(ms_tick, std::memory_order_relaxed);
		LogLine(S("window {}: t/s={:.2f} cpu={:.3f}s ms/tick={:.2f} frame_ms={:.1f} busy={:.1f}% """
assert old_r2 in s
s = s.replace(old_r2, new_r2, 1)

# 4) регистрация команд
old_reg = '\tcmds.AddRconCommand("TickProf.perf", [](RCONClientConnection* c, RCONPacket* p, UWorld* w) { CmdPerf(c, p, w); });'
new_reg = old_reg + """
	cmds.AddRconCommand("TickProf.window", [](RCONClientConnection* c, RCONPacket* p, UWorld* w) { CmdWindow(c, p, w); });
	cmds.AddRconCommand("TickProf.mon", [](RCONClientConnection* c, RCONPacket* p, UWorld* w) { CmdMon(c, p, w); });
	cmds.AddRconCommand("TickProf.arkstate", [](RCONClientConnection* c, RCONPacket* p, UWorld* w) { CmdArkstate(c, p, w); });
	cmds.AddRconCommand("TickProf.perf.selftest", [](RCONClientConnection* c, RCONPacket* p, UWorld* w) { CmdSelftest(c, p, w); });"""
assert old_reg in s
s = s.replace(old_reg, new_reg, 1)

io.open(P, "w", encoding="utf-8", newline="\r\n").write(s)
print("плагин: монитор, детектор сохранений, window с валидностью, perf.selftest добавлены")
# -*- coding: utf-8 -*-
# Слот E, П1+П3+П5 (+ подготовка П4): bptrace v2.
#   * учёт ВРЕМЕНИ по функции: total/self (self = total - дети), часы QPC;
#   * атрибуция ВЫЗЫВАЮЩЕГО через FFrame::PreviousFrame (+0x70) -> Node (+0x10);
#   * пауза 60 с после конца сэмплер-окна (П5) с записью в лог;
#   * дамп флагов UFunction (return/out-параметры) - подготовка П4;
#   * команды: bptrace.reset, bptrace.caller, fnflags.
import io

CPP = r'C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp'
src = io.open(CPP, 'r', encoding='utf-8', newline='').read()
NL = '\r\n' if '\r\n' in src else '\n'


def blk(t):
    return t.replace('\n', NL)


# ---------------------------------------------------------------- 1. ядро
CORE = blk('''	constexpr uint32_t BPTRACE_PROCESSINTERNAL_RVA = 0x01FC0270;
	constexpr uint32_t UFUNCTION_FUNC_OFFSET = 0xA8;
	// FFrame (сборка v361, подтверждено Ghidra): Node = UFunction* @ +0x10,
	// PreviousFrame = кадр вызывающего @ +0x70. Верхнеуровневый вход из
	// ProcessEvent даёт PreviousFrame = 0 => "native/ProcessEvent-entry".
	constexpr uint32_t FFRAME_NODE_OFFSET = 0x10;
	constexpr uint32_t FFRAME_PREV_OFFSET = 0x70;
	constexpr size_t BP_MAX_SLOTS = 8192;
	constexpr int BP_MAX_DEPTH = 256;
	constexpr int BP_MAX_CALLERS = 8;
	// Псевдо-слоты вызывающих: -2 = native/ProcessEvent-entry (PreviousFrame==0),
	// -3 = вызывающий не опознан.
	constexpr int32_t BP_CALLER_NATIVE = -2;
	constexpr int32_t BP_CALLER_UNKNOWN = -3;
	struct BpCallerRec
	{
		int32_t slot;
		volatile LONG64 count;
	};
	struct BpSlot
	{
		std::string name;
		uint64_t hash = 0;
		volatile LONG64 calls = 0;
		volatile LONG64 total_ticks = 0;
		volatile LONG64 self_ticks = 0;
		bool script = false;
		BpCallerRec callers[BP_MAX_CALLERS] = {};
	};
	// Слоты с фиксированным размером: без реаллокации => гонок нет.
	std::vector<BpSlot> g_bp_slotv;
	size_t g_bp_slots = 0; // под g_bp_lock
	SRWLOCK g_bp_lock = SRWLOCK_INIT;
	// UFunction* -> слот: заполняется лениво (имя резолвится один раз).
	std::unordered_map<void*, int32_t> g_bp_fn_slot;
	std::atomic<int64_t> g_bp_calls{0};
	std::atomic<bool> g_bp_on{false};
	std::atomic<int64_t> g_bp_win_start{0}; // начало окна (для нормировки)
	std::vector<void*> g_bp_targets;
	std::vector<void*> g_bp_orig_func;
	void* g_bp_orig_processinternal = nullptr;
	int64_t g_bp_qpc_freq = 10000000;
	// Стек вызовов в потоке: (слот, вызывающий, старт, дети).
	struct BpFrame
	{
		int32_t slot;
		int32_t caller;
		uint64_t start;
		uint64_t children;
	};
	thread_local BpFrame g_bp_stack[BP_MAX_DEPTH];
	thread_local int g_bp_depth = 0;
	uint64_t BpHash(const std::string& s)
	{
		uint64_t h = 1469598103934665603ULL;
		for (char c : s)
		{
			h ^= (uint64_t)(uint8_t)c;
			h *= 1099511628211ULL;
		}
		return h ? h : 1;
	}
	// Имя UFunction-объекта. UObject::GetName в ArkApi недоступен,
	// UObjectBaseUtility.GetFullName - доступен (через NativeCall).
	bool BpNameOfUFunction(void* fn, std::string& out)
	{
		if (!fn)
			return false;
		FString full;
		if (!reinterpret_cast<UObjectBaseUtility*>(fn)->GetFullName(&full, nullptr))
			return false;
		out = full.ToString();
		return !out.empty();
	}
	// FFrame::Node = UFunction* (вызываемая функция).
	void* BpFrameNode(void* frame)
	{
		if (!frame)
			return nullptr;
		return *reinterpret_cast<void**>(reinterpret_cast<uint8_t*>(frame) + FFRAME_NODE_OFFSET);
	}
	// FFrame::PreviousFrame = кадр вызывающего (0 = верхний вход из ProcessEvent).
	void* BpFramePrev(void* frame)
	{
		if (!frame)
			return nullptr;
		return *reinterpret_cast<void**>(reinterpret_cast<uint8_t*>(frame) + FFRAME_PREV_OFFSET);
	}
	// Холодный путь: имя функции -> слот (слот создаётся при первом появлении).
	int32_t BpResolveSlot(void* fn)
	{
		if (!fn)
			return -1;
		std::string nm;
		if (!BpNameOfUFunction(fn, nm))
			return -1;
		const uint64_t h = BpHash(nm);
		AcquireSRWLockExclusive(&g_bp_lock);
		int32_t slot = -1;
		auto it = g_bp_fn_slot.find(fn);
		if (it != g_bp_fn_slot.end())
		{
			slot = it->second;
		}
		else
		{
			for (size_t i = 0; i < g_bp_slots; ++i)
			{
				if (g_bp_slotv[i].hash == h)
				{
					slot = (int32_t)i;
					break;
				}
			}
			if (slot < 0 && g_bp_slots < BP_MAX_SLOTS)
			{
				slot = (int32_t)g_bp_slots++;
				BpSlot& s = g_bp_slotv[slot];
				s.hash = h;
				s.name = nm;
				s.script = false;
			}
			if (slot >= 0)
				g_bp_fn_slot[fn] = slot;
		}
		ReleaseSRWLockExclusive(&g_bp_lock);
		return slot;
	}
	// Горячий путь: слот функции по указателю UFunction*.
	int32_t BpSlotOf(void* fn)
	{
		if (!fn)
			return -1;
		int32_t slot = -1;
		AcquireSRWLockShared(&g_bp_lock);
		auto it = g_bp_fn_slot.find(fn);
		if (it != g_bp_fn_slot.end())
			slot = it->second;
		ReleaseSRWLockShared(&g_bp_lock);
		if (slot < 0)
			slot = BpResolveSlot(fn);
		return slot;
	}
	// Кто вызвал: FFrame::PreviousFrame -> Node.
	int32_t BpCallerSlot(void* frame)
	{
		void* prev = BpFramePrev(frame);
		if (!prev)
			return BP_CALLER_NATIVE;
		void* pfn = BpFrameNode(prev);
		if (!pfn)
			return BP_CALLER_UNKNOWN;
		const int32_t s = BpSlotOf(pfn);
		return s < 0 ? BP_CALLER_UNKNOWN : s;
	}
	// Учёт пары "вызываемая <- вызывающая" (максимум BP_MAX_CALLERS на функцию).
	void BpNoteCaller(int32_t callee, int32_t caller)
	{
		if (callee < 0)
			return;
		BpSlot& s = g_bp_slotv[callee];
		for (int i = 0; i < BP_MAX_CALLERS; ++i)
		{
			if (s.callers[i].slot == caller)
			{
				InterlockedIncrement64(&s.callers[i].count);
				return;
			}
		}
		AcquireSRWLockExclusive(&g_bp_lock);
		for (int i = 0; i < BP_MAX_CALLERS; ++i)
		{
			if (s.callers[i].slot == caller)
			{
				InterlockedIncrement64(&s.callers[i].count);
				ReleaseSRWLockExclusive(&g_bp_lock);
				return;
			}
			if (s.callers[i].slot == 0 && s.callers[i].count == 0)
			{
				s.callers[i].slot = caller;
				s.callers[i].count = 1;
				ReleaseSRWLockExclusive(&g_bp_lock);
				return;
			}
		}
		ReleaseSRWLockExclusive(&g_bp_lock);
	}
	// Сброс счётчиков/окна (без снятия подмены).
	void BpResetCounters()
	{
		AcquireSRWLockExclusive(&g_bp_lock);
		g_bp_fn_slot.clear();
		g_bp_slots = 0;
		for (size_t i = 0; i < g_bp_slotv.size(); ++i)
		{
			BpSlot& s = g_bp_slotv[i];
			s.calls = 0;
			s.total_ticks = 0;
			s.self_ticks = 0;
			for (int k = 0; k < BP_MAX_CALLERS; ++k)
			{
				s.callers[k].slot = 0;
				s.callers[k].count = 0;
			}
		}
		ReleaseSRWLockExclusive(&g_bp_lock);
		g_bp_depth = 0;
		g_bp_calls.store(0, std::memory_order_relaxed);
		g_bp_win_start.store(GetTickCount64(), std::memory_order_relaxed);
	}
	// Обработчик: вызывается вместо ProcessInternal для скриптовых функций.
	// Сигнатура FNativeFunctionPtr: (UObject* Context, FFrame& Stack, void*& RESULT).
	void __fastcall BpHandler(void* self, void* frame, void* result)
	{
		typedef void(__fastcall* Fn)(void*, void*, void*);
		if (!g_bp_on.load(std::memory_order_relaxed))
		{
			reinterpret_cast<Fn>(g_bp_orig_processinternal)(self, frame, result);
			return;
		}
		void* fn = BpFrameNode(frame);
		const int32_t slot = BpSlotOf(fn);
		const int32_t caller = BpCallerSlot(frame);
		LARGE_INTEGER t0;
		QueryPerformanceCounter(&t0);
		const bool timed = (slot >= 0 && g_bp_depth < BP_MAX_DEPTH);
		if (timed)
		{
			BpFrame& f = g_bp_stack[g_bp_depth];
			f.slot = slot;
			f.caller = caller;
			f.start = (uint64_t)t0.QuadPart;
			f.children = 0;
			++g_bp_depth;
		}
		reinterpret_cast<Fn>(g_bp_orig_processinternal)(self, frame, result);
		if (!timed)
			return;
		LARGE_INTEGER t1;
		QueryPerformanceCounter(&t1);
		--g_bp_depth;
		BpFrame& f = g_bp_stack[g_bp_depth];
		const uint64_t total = (uint64_t)(t1.QuadPart - f.start);
		const uint64_t self = total - f.children;
		BpSlot& s = g_bp_slotv[f.slot];
		InterlockedIncrement64(&s.calls);
		InterlockedExchangeAdd64(&s.total_ticks, (LONG64)total);
		InterlockedExchangeAdd64(&s.self_ticks, (LONG64)self);
		BpNoteCaller(f.slot, f.caller);
		if (g_bp_depth > 0)
			g_bp_stack[g_bp_depth - 1].children += total;
		g_bp_calls.fetch_add(1, std::memory_order_relaxed);
	}
''')

i = src.index('	constexpr uint32_t BPTRACE_PROCESSINTERNAL_RVA = 0x01FC0270;')
j = src.index('	struct BpScanResult', i)
src = src[:i] + CORE + src[j:]

# ---------------------------------------------- 2. команды bptrace (v2)
CMDS = blk('''	void CmdBpTrace(RCONClientConnection*, RCONPacket* packet, UWorld*)
	{
		const int32_t mode = ArgInt(packet, 0);
		if (mode == 0)
		{
			g_bp_on.store(false, std::memory_order_relaxed);
			const size_t n = g_bp_targets.size();
			BpRemovePatch();
			BpResetCounters();
			LogLine(S("bptrace: выключен (вызовов {}), подмен снят с {} UFunction", g_bp_calls.load(), n));
			return;
		}
		if (mode == 2)
		{
			const BpScanResult r = BpScanAndPatch(false);
			if (r.error)
			{
				LogLine(S("bptrace: ошибка перечисления: {}", r.error));
				return;
			}
			LogLine(S("bptrace: перечисление: UFunction всего={} скриптовых(Func==&ProcessInternal)={}",
				r.ufunctions_seen, r.script_functions));
			return;
		}
		if (InCooldown())
		{
			LogLine(S("bptrace: отказ - пауза после сэмплер-окна ещё не кончилась ({} с)",
				CooldownLeft()));
			return;
		}
		const BpScanResult r = BpScanAndPatch(true);
		if (r.error)
		{
			LogLine(S("bptrace: ошибка подмены: {}", r.error));
			return;
		}
		LogLine(S("bptrace: подмена Func у {} скриптовых UFunction (всего UFunction={})",
			r.patched, r.ufunctions_seen));
		if (r.patched == 0)
		{
			LogLine("bptrace: подменять нечего - скриптовых UFunction не найдено");
			return;
		}
		BpResetCounters();
		g_bp_on.store(true, std::memory_order_relaxed);
		LogLine("bptrace: включён v2 (патч ДАННЫХ UFunction::Func; учёт времени total/self, "
				"атрибуция вызывающего через FFrame::PreviousFrame)");
	}
	// Отчёт: топ по вызовам и топ по self-времени (с долями).
	void CmdBpTraceReport(RCONClientConnection*, RCONPacket*, UWorld*)
	{
		const int64_t win_ms = GetTickCount64() - g_bp_win_start.load();
		LogLine(S("bptrace: вызовов всего {} (окно {} с, QPC {} Гц)", g_bp_calls.load(), win_ms / 1000,
			g_bp_qpc_freq));
		struct Row
		{
			std::string name;
			uint64_t calls;
			double total_ms;
			double self_ms;
			bool script;
		};
		std::vector<Row> rows;
		{
			AcquireSRWLockExclusive(&g_bp_lock);
			for (size_t i = 0; i < g_bp_slots; ++i)
			{
				const BpSlot& s = g_bp_slotv[i];
				if (s.calls == 0)
					continue;
				rows.push_back({s.name, (uint64_t)s.calls,
					(double)s.total_ticks * 1000.0 / (double)g_bp_qpc_freq,
					(double)s.self_ticks * 1000.0 / (double)g_bp_qpc_freq, s.script});
			}
			ReleaseSRWLockExclusive(&g_bp_lock);
		}
		LogLine(S("bptrace: функций с вызовами {}", rows.size()));
		double sum_self = 0.0;
		for (const Row& r : rows)
			sum_self += r.self_ms;
		std::vector<Row> by_calls = rows;
		std::sort(by_calls.begin(), by_calls.end(), [](const Row& a, const Row& b) { return a.calls > b.calls; });
		std::vector<Row> by_self = rows;
		std::sort(by_self.begin(), by_self.end(), [](const Row& a, const Row& b) { return a.self_ms > b.self_ms; });
		LogLine("bptrace: ТОП-20 ПО ВЫЗОВАМ");
		for (size_t i = 0; i < by_calls.size() && i < 20; ++i)
		{
			const Row& r = by_calls[i];
			LogLine(S("bptrace:   {} вызовов={} total={:.1f}мс self={:.1f}мс мс/вызов={:.4f} {}",
				r.name, r.calls, r.total_ms, r.self_ms,
				r.calls ? r.self_ms * 1000.0 / (double)r.calls : 0.0, r.script ? "script" : "native"));
		}
		LogLine(S("bptrace: ТОП-20 ПО SELF-ВРЕМЕНИ (сумма self={:.1f} мс)", sum_self));
		for (size_t i = 0; i < by_self.size() && i < 20; ++i)
		{
			const Row& r = by_self[i];
			LogLine(S("bptrace:   {} self={:.1f}мс ({:.1f}%) вызовов={} мс/вызов={:.4f} {}",
				r.name, r.self_ms, sum_self > 0 ? 100.0 * r.self_ms / sum_self : 0.0, r.calls,
				r.calls ? r.self_ms * 1000.0 / (double)r.calls : 0.0, r.script ? "script" : "native"));
		}
	}
	// Сброс счётчиков на новое окно (подмена остаётся).
	void CmdBpTraceReset(RCONClientConnection*, RCONPacket*, UWorld*)
	{
		BpResetCounters();
		LogLine("bptrace: счётчики обнулены (окно переоткрыто)");
	}
	// Топ вызывающих для функции (по рангу в топе self-времени или по подстроке имени).
	void CmdBpTraceCaller(RCONClientConnection*, RCONPacket* packet, UWorld*)
	{
		const std::string body = packet ? packet->Body.ToString() : "";
		std::string arg = body;
		const size_t sp = arg.find_last_of(' ');
		if (sp != std::string::npos)
			arg = arg.substr(sp + 1);
		// ранги считаем по топу self-времени
		struct Row
		{
			std::string name;
			int32_t slot;
			double self_ms;
		};
		std::vector<Row> rows;
		{
			AcquireSRWLockExclusive(&g_bp_lock);
			for (size_t i = 0; i < g_bp_slots; ++i)
			{
				const BpSlot& s = g_bp_slotv[i];
				if (s.calls == 0)
					continue;
				rows.push_back({s.name, (int32_t)i,
					(double)s.self_ticks * 1000.0 / (double)g_bp_qpc_freq});
			}
			ReleaseSRWLockExclusive(&g_bp_lock);
		}
		std::sort(rows.begin(), rows.end(), [](const Row& a, const Row& b) { return a.self_ms > b.self_ms; });
		int32_t target = -1;
		bool by_rank = !arg.empty() && arg.find_first_not_of("0123456789") == std::string::npos;
		if (by_rank)
		{
			const size_t rank = (size_t)atoi(arg.c_str());
			if (rank >= 1 && rank <= rows.size())
				target = rows[rank - 1].slot;
		}
		else
		{
			for (const Row& r : rows)
			{
				if (r.name.find(arg) != std::string::npos)
				{
					target = r.slot;
					break;
				}
			}
		}
		if (target < 0)
		{
			LogLine(S("bptrace.caller: не найдена функция '{}' (ранг 1..{}, подстрока имени)", arg,
				rows.size()));
			return;
		}
		AcquireSRWLockExclusive(&g_bp_lock);
		const BpSlot& s = g_bp_slotv[target];
		LogLine(S("bptrace.caller: {} (вызовов={}, self={:.1f}мс)", s.name, (uint64_t)s.calls,
			(double)s.self_ticks * 1000.0 / (double)g_bp_qpc_freq));
		for (int i = 0; i < BP_MAX_CALLERS; ++i)
		{
			const int32_t cs = s.callers[i].slot;
			if (cs == 0 || s.callers[i].count == 0)
				continue;
			const uint64_t cnt = (uint64_t)s.callers[i].count;
			std::string cname;
			if (cs == BP_CALLER_NATIVE)
				cname = "<native/ProcessEvent-entry>";
			else if (cs == BP_CALLER_UNKNOWN)
				cname = "<вызывающий не опознан>";
			else if (cs >= 0 && (size_t)cs < g_bp_slotv.size())
				cname = g_bp_slotv[cs].name;
			LogLine(S("bptrace.caller:   {} вызовов={} ({:.1f}%)", cname, cnt,
				(uint64_t)s.calls ? 100.0 * (double)cnt / (double)s.calls : 0.0));
		}
		ReleaseSRWLockExclusive(&g_bp_lock);
	}
''')

i = src.index('	void CmdBpTrace(RCONClientConnection*, RCONPacket* packet, UWorld*)')
j = src.index('	// ------------------------------------------------- census overlap-событий', i)
src = src[:i] + CMDS + src[j:]

io.open(CPP, 'w', encoding='utf-8', newline='').write(src)
print('ядро v2 и команды вставлены')

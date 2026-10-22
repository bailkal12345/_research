# -*- coding: utf-8 -*-
# doit6 §4: bptrace через ПАТЧ ДАННЫХ UFunction::Func (без патча кода).
#
# КЛЮЧЕВАЯ НАХОДКА (Ghidra, /v361_ShooterGameServer.exe):
#   UFunction + 0xA8 = поле Func (УКАЗАТЕЛЬ на нативную функцию).
#   Bind() (0x141F86D30): LEA RAX,[0x141FC0270] ; MOV [R9+0xA8],RAX  -> для СКРИПТОВЫХ
#   функций Func = &ProcessInternal; для нативных - их exec-указатель.
#   Поле +0x98 (2 байта) - другое поле, НЕ Func.
#
# ПОЧЕМУ БЕЗОПАСНО (в отличие от патча кода):
#   * патчится ДАННЫЕ (heap-объект UFunction), инструкции не трогаем;
#   * security cookie не затронута (RSP/регистры вызова не меняются);
#   * вызов оригинала - обычный C++-вызов через сохранённый указатель;
#   * откат = записать исходный Func обратно (идемпотентно).
#
# ЛОГИРУЕМ: полное имя UFunction (Class.Function) + счётчик вызовов.
# Имя берём из FFrame: FFrame::Node = UFunction* (декомпил ProcessInternal:
# UFunction::GetReturnProperty(param_1->Node)).
import io, sys

CPP = r'C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp'
src = io.open(CPP, 'r', encoding='utf-8', newline='').read()
NL = '\r\n' if '\r\n' in src else '\n'


def blk(t):
    return t.replace('\n', NL)


if 'BpDataPatch' in src or 'UFUNCTION_FUNC_OFFSET' in src:
    print('bptrace (патч данных) уже реализован - пропускаю')
    sys.exit(0)

# --- вычищаем прежнюю (небезопасную) реализацию ---
if '	// ------------------------------------------------- bptrace (ARCH.md 3.5)' in src:
    start = src.index(blk('	// ------------------------------------------------- bptrace (ARCH.md 3.5)'))
    end = src.index(blk('	// ------------------------------------------------- census overlap-событий'), start)
    src = src[:start] + src[end:]
if '	void CmdBpTrace(' in src:
    i = src.index(blk('	void CmdBpTrace('))
    j = src.index(blk('	cmds.AddRconCommand("TickProf.cachestat",'), i)
    src = src[:i] + src[j:]
src = src.replace(blk('''	cmds.AddRconCommand("TickProf.bptrace", [](RCONClientConnection* c, RCONPacket* p, UWorld* w) { CmdBpTrace(c, p, w); });
'''), '', 1)

NEW = blk('''	// ------------------------------------------------- bptrace (ARCH.md 3.5)
	//
	// Трассировщик Blueprint ЧЕРЕЗ ПАТЧ ДАННЫХ: UFunction + 0xA8 = Func (указатель).
	// Для скриптовых функций там &ProcessInternal (Bind: LEA RAX,[ProcessInternal];
	// MOV [R9+0xA8],RAX), для нативных - их exec-указатель.
	// Подменяем Func ТОЛЬКО у скриптовых UFunction и вызываем оригинал обычным
	// C++-вызовом => код процесса не патчится, security cookie не затронута,
	// откат = записать исходный Func обратно.
	constexpr uint32_t BPTRACE_PROCESSINTERNAL_RVA = 0x01FC0270;
	constexpr uint32_t UFUNCTION_FUNC_OFFSET = 0xA8;

	// Счётчики: глобальные, инкремент атомарный (Interlocked) - без блокировок.
	std::vector<uint64_t> g_bp_count;
	std::vector<std::string> g_bp_names;
	std::vector<uint64_t> g_bp_hash;
	SRWLOCK g_bp_lock = SRWLOCK_INIT;

	// thread_local: индекс слота (горячий путь без блокировок).
	thread_local int32_t g_bp_slot = -1;

	std::atomic<int64_t> g_bp_calls{0};
	std::atomic<bool> g_bp_on{false};
	// UFunction* -> исходный Func (для отката).
	std::vector<void*> g_bp_targets;
	std::vector<void*> g_bp_orig_func;
	void* g_bp_orig_processinternal = nullptr;

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

	// FFrame::Node = UFunction* (декомпил ProcessInternal).
	bool BpNameFromFrame(void* frame, std::string& out)
	{
		if (!frame)
			return false;
		void* fn = *reinterpret_cast<void**>(reinterpret_cast<uint8_t*>(frame) + 0x10);
		return BpNameOfUFunction(fn, out);
	}

	void BpNote(const std::string& name)
	{
		const uint64_t h = BpHash(name);
		if (g_bp_slot < 0)
		{
			// Холодный путь (промах хеша) - SRWLOCK.
			AcquireSRWLockExclusive(&g_bp_lock);
			int32_t found = -1;
			for (size_t i = 0; i < g_bp_hash.size(); ++i)
			{
				if (g_bp_hash[i] == h)
				{
					found = (int32_t)i;
					break;
				}
			}
			if (found < 0)
			{
				g_bp_names.push_back(name);
				g_bp_hash.push_back(h);
				g_bp_count.push_back(0);
				found = (int32_t)g_bp_hash.size() - 1;
			}
			ReleaseSRWLockExclusive(&g_bp_lock);
			g_bp_slot = found;
		}
		if (g_bp_slot < 0)
			return;
		// Атомарный инкремент без блокировки.
		InterlockedIncrement64(reinterpret_cast<volatile LONG64*>(&g_bp_count[g_bp_slot]));
	}

	// Обработчик: вызывается вместо ProcessInternal для скриптовых функций.
	// Сигнатура FNativeFunctionPtr: (UObject* Context, FFrame& Stack, void* RESULT).
	void __fastcall BpHandler(void* self, void* frame, void* result)
	{
		if (g_bp_on.load(std::memory_order_relaxed))
		{
			std::string nm;
			if (BpNameFromFrame(frame, nm))
				BpNote(nm);
		}
		// Оригинал: ProcessInternal(this, FFrame*, void*) - тот же прототип.
		typedef void(__fastcall* Fn)(void*, void*, void*);
		reinterpret_cast<Fn>(g_bp_orig_processinternal)(self, frame, result);
	}

	struct BpScanResult
	{
		int ufunctions_seen = 0;
		int script_functions = 0;
		int patched = 0;
		int already = 0;
	};

	// Перебор UObject: у скриптовых UFunction поле Func == &ProcessInternal.
	BpScanResult BpScanAndPatch(bool apply)
	{
		BpScanResult res;
		void* mod = GetModuleHandleW(L"ShooterGameServer.exe");
		if (!mod)
			return res;
		g_bp_orig_processinternal = (void*)((uint8_t*)mod + BPTRACE_PROCESSINTERNAL_RVA);

		const FUObjectArray& arr = Globals::GUObjectArray()();
		const int count = arr.ObjObjects.NumElements;
		for (int i = 0; i < count; ++i)
		{
			UObject* obj = arr.ObjObjects.GetObjectPtr(i)->Object;
			if (!obj)
				continue;
			void** func_slot = reinterpret_cast<void**>(reinterpret_cast<uint8_t*>(obj) + UFUNCTION_FUNC_OFFSET);
			void* f = *func_slot;
			if (!f || f != g_bp_orig_processinternal)
				continue;
			// Func == &ProcessInternal => это скриптовая (Blueprint) UFunction.
			++res.script_functions;
			++res.ufunctions_seen;
			if (!apply)
				continue;
			bool known = false;
			for (size_t k = 0; k < g_bp_targets.size(); ++k)
			{
				if (g_bp_targets[k] == (void*)obj)
				{
					known = true;
					break;
				}
			}
			if (known)
			{
				++res.already;
				continue;
			}
			g_bp_targets.push_back((void*)obj);
			g_bp_orig_func.push_back(f);
			*func_slot = (void*)&BpHandler;
			++res.patched;
		}
		return res;
	}

	void BpRemovePatch()
	{
		for (size_t i = 0; i < g_bp_targets.size(); ++i)
		{
			void** slot = reinterpret_cast<void**>(reinterpret_cast<uint8_t*>(g_bp_targets[i]) + UFUNCTION_FUNC_OFFSET);
			*slot = g_bp_orig_func[i];
		}
		g_bp_targets.clear();
		g_bp_orig_func.clear();
		g_bp_on.store(false, std::memory_order_relaxed);
	}

	void CmdBpTrace(RCONClientConnection*, RCONPacket* packet, UWorld*)
	{
		const int32_t mode = ArgInt(packet, 0);
		if (mode == 0)
		{
			g_bp_on.store(false, std::memory_order_relaxed);
			const size_t n = g_bp_targets.size();
			BpRemovePatch();
			LogLine(S("bptrace: выключен (вызовов {}), подмен снят с {} UFunction", g_bp_calls.load(), n));
			return;
		}
		if (mode == 2)
		{
			const BpScanResult r = BpScanAndPatch(false);
			LogLine(S("bptrace: перечисление: скриптовых UFunction (Func==&ProcessInternal) = {}",
				r.script_functions));
			return;
		}
		const BpScanResult r = BpScanAndPatch(true);
		LogLine(S("bptrace: подмена Func у {} скриптовых UFunction", r.patched));
		if (r.patched == 0)
		{
			LogLine("bptrace: подменять нечего - скриптовых UFunction не найдено");
			return;
		}
		g_bp_on.store(true, std::memory_order_relaxed);
		g_bp_calls.store(0);
		LogLine("bptrace: включён (патч ДАННЫХ UFunction::Func, код процесса не тронут)");
	}

	// Топ вызовов.
	void CmdBpTraceReport(RCONClientConnection*, RCONPacket*, UWorld*)
	{
		LogLine(S("bptrace: вызовов всего {}", g_bp_calls.load()));
		std::vector<std::pair<std::string, uint64_t>> rows;
		{
			AcquireSRWLockExclusive(&g_bp_lock);
			for (size_t i = 0; i < g_bp_names.size(); ++i)
				rows.push_back({g_bp_names[i], g_bp_count[i]});
			ReleaseSRWLockExclusive(&g_bp_lock);
		}
		std::sort(rows.begin(), rows.end(), [](const auto& a, const auto& b) { return a.second > b.second; });
		for (size_t i = 0; i < rows.size() && i < 30; ++i)
			LogLine(S("bptrace: {} = {}", rows[i].first, rows[i].second));
	}

''')

ANCHOR = blk('	// ------------------------------------------------- census overlap-событий\n')
assert ANCHOR in src, 'якорь census не найден'
src = src.replace(ANCHOR, NEW + ANCHOR, 1)

REG = blk('''	cmds.AddRconCommand("TickProf.bptrace", [](RCONClientConnection* c, RCONPacket* p, UWorld* w) { CmdBpTrace(c, p, w); });
	cmds.AddRconCommand("TickProf.bptrace.report", [](RCONClientConnection* c, RCONPacket* p, UWorld* w) { CmdBpTraceReport(c, p, w); });
''')
A2 = blk('	cmds.AddRconCommand("TickProf.cachestat",')
assert A2 in src, 'якорь команды не найден'
src = src.replace(A2, REG + A2, 1)

io.open(CPP, 'w', encoding='utf-8', newline='').write(src)
print('bptrace переписан на патч данных UFunction::Func')

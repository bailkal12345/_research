# -*- coding: utf-8 -*-
# Переписывает ядро bptrace:
#  - фиксированный массив слотов (нет реаллокации => нет гонок);
#  - слот ищется по ХЕШУ ИМЕНИ (баг: thread_local g_bp_slot кэшировал первый
#    слот навсегда => все вызовы схлопывались в один счётчик);
#  - имя резолвится ОДИН раз на UFunction (лениво), дальше поиск по указателю;
#  - отчёт/сброс приведены к новой структуре.
import io

CPP = r'C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp'
src = io.open(CPP, 'r', encoding='utf-8', newline='').read()
NL = '\r\n' if '\r\n' in src else '\n'


def blk(t):
    """шаблон (с \n) -> переводы строк файла"""
    return t.replace('\n', NL)


NEW_CORE = blk('''	constexpr uint32_t BPTRACE_PROCESSINTERNAL_RVA = 0x01FC0270;
	constexpr uint32_t UFUNCTION_FUNC_OFFSET = 0xA8;
	// Слоты счётчиков - фиксированный массив: без реаллокации => гонок нет.
	constexpr size_t BP_MAX_SLOTS = 65536;
	std::string g_bp_names[BP_MAX_SLOTS];
	uint64_t g_bp_hash[BP_MAX_SLOTS] = {0};
	volatile LONG64 g_bp_count[BP_MAX_SLOTS] = {0};
	size_t g_bp_slots = 0; // под g_bp_lock
	SRWLOCK g_bp_lock = SRWLOCK_INIT;
	// UFunction* -> слот: заполняется лениво (имя резолвится один раз на функцию).
	std::unordered_map<void*, int32_t> g_bp_fn_slot;
	// Горячий путь: последняя пара (функция -> слот) в потоке.
	thread_local void* g_bp_last_fn = nullptr;
	thread_local int32_t g_bp_last_slot = -1;
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
	void* BpFrameNode(void* frame)
	{
		if (!frame)
			return nullptr;
		return *reinterpret_cast<void**>(reinterpret_cast<uint8_t*>(frame) + 0x10);
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
				if (g_bp_hash[i] == h)
				{
					slot = (int32_t)i;
					break;
				}
			}
			if (slot < 0 && g_bp_slots < BP_MAX_SLOTS)
			{
				slot = (int32_t)g_bp_slots++;
				g_bp_hash[slot] = h;
				g_bp_names[slot] = nm;
				g_bp_count[slot] = 0;
			}
			if (slot >= 0)
				g_bp_fn_slot[fn] = slot;
		}
		ReleaseSRWLockExclusive(&g_bp_lock);
		return slot;
	}
	// Сброс счётчиков/имён (без снятия подмены).
	void BpResetCounters()
	{
		AcquireSRWLockExclusive(&g_bp_lock);
		g_bp_fn_slot.clear();
		g_bp_slots = 0;
		std::memset((void*)g_bp_count, 0, sizeof(g_bp_count));
		ReleaseSRWLockExclusive(&g_bp_lock);
		g_bp_last_fn = nullptr;
		g_bp_last_slot = -1;
		g_bp_calls.store(0, std::memory_order_relaxed);
	}
	// Обработчик: вызывается вместо ProcessInternal для скриптовых функций.
	// Сигнатура FNativeFunctionPtr: (UObject* Context, FFrame& Stack, void*& RESULT).
	void __fastcall BpHandler(void* self, void* frame, void* result)
	{
		if (g_bp_on.load(std::memory_order_relaxed))
		{
			void* fn = BpFrameNode(frame);
			int32_t slot = -1;
			if (fn == g_bp_last_fn)
			{
				slot = g_bp_last_slot;
			}
			else
			{
				AcquireSRWLockShared(&g_bp_lock);
				auto it = g_bp_fn_slot.find(fn);
				if (it != g_bp_fn_slot.end())
					slot = it->second;
				ReleaseSRWLockShared(&g_bp_lock);
				if (slot < 0)
					slot = BpResolveSlot(fn);
				g_bp_last_fn = fn;
				g_bp_last_slot = slot;
			}
			if (slot >= 0)
				InterlockedIncrement64(&g_bp_count[slot]);
			g_bp_calls.fetch_add(1, std::memory_order_relaxed);
		}
		// Оригинал: ProcessInternal(this, FFrame*, void*) - тот же прототип.
		typedef void(__fastcall* Fn)(void*, void*, void*);
		reinterpret_cast<Fn>(g_bp_orig_processinternal)(self, frame, result);
	}
''')

# --- замена ядра ---
i = src.index('	constexpr uint32_t BPTRACE_PROCESSINTERNAL_RVA = 0x01FC0270;')
j = src.index('	struct BpScanResult', i)
src = src[:i] + NEW_CORE + src[j:]

# --- сброс счётчиков при включении ---
old_on = blk('''		g_bp_on.store(true, std::memory_order_relaxed);
		g_bp_calls.store(0);''')
new_on = blk('''		BpResetCounters();
		g_bp_on.store(true, std::memory_order_relaxed);''')
assert old_on in src, 'включение не найдено'
src = src.replace(old_on, new_on, 1)

# --- отчёт по новой структуре ---
old_rep = blk('''		LogLine(S("bptrace: вызовов всего {}", g_bp_calls.load()));
		std::vector<std::pair<std::string, uint64_t>> rows;
		{
			AcquireSRWLockExclusive(&g_bp_lock);
			for (size_t i = 0; i < g_bp_names.size(); ++i)
				rows.push_back({g_bp_names[i], g_bp_count[i]});
			ReleaseSRWLockExclusive(&g_bp_lock);
		}''')
new_rep = blk('''		LogLine(S("bptrace: вызовов всего {}", g_bp_calls.load()));
		std::vector<std::pair<std::string, uint64_t>> rows;
		{
			AcquireSRWLockExclusive(&g_bp_lock);
			for (size_t i = 0; i < g_bp_slots; ++i)
				rows.push_back({g_bp_names[i], (uint64_t)g_bp_count[i]});
			ReleaseSRWLockExclusive(&g_bp_lock);
		}
		LogLine(S("bptrace: различных функций {}", rows.size()));''')
assert old_rep in src, 'отчёт не найден'
src = src.replace(old_rep, new_rep, 1)

# --- снятие подмены: чистим и счётчики ---
old_off = blk('''			g_bp_on.store(false, std::memory_order_relaxed);
			const size_t n = g_bp_targets.size();
			BpRemovePatch();''')
new_off = blk('''			g_bp_on.store(false, std::memory_order_relaxed);
			const size_t n = g_bp_targets.size();
			BpRemovePatch();
			BpResetCounters();''')
assert old_off in src, 'снятие не найдено'
src = src.replace(old_off, new_off, 1)

io.open(CPP, 'w', encoding='utf-8', newline='').write(src)
print('ядро bptrace переписано')

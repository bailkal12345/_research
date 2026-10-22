# -*- coding: utf-8 -*-
# Слот E, часть 2: П5 (пауза 60 с после сэмплер-окна), инициализация слотов/частоты
# QPC, дамп флагов UFunction (подготовка П4), регистрация новых команд.
import io

CPP = r'C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp'
src = io.open(CPP, 'r', encoding='utf-8', newline='').read()
NL = '\r\n' if '\r\n' in src else '\n'


def blk(t):
    return t.replace('\n', NL)


def _norm(a):
    # якоря всегда нормализуем под переводы строк файла
    return a.replace(chr(13) + chr(10), chr(10)).replace(chr(10), NL)


def insert_before(anchor, text, s):
    a = _norm(anchor)
    i = s.index(a)
    return s[:i] + text + s[i:]


def insert_after(anchor, text, s):
    a = _norm(anchor)
    i = s.index(a) + len(a)
    return s[:i] + text + s[i:]


# ---------------------------------------- 1. пауза 60 с (П5) + флаги (П4)
COOLDOWN = blk('''	// ------------------------------------------------- пауза после сэмплер-окна (П5)
	// Слот D: краш плагина находился вручную через 2-3 с после конца окна
	// сэмплирования. Правило: после конца окна - 60 с тишины перед новыми
	// измерениями, срабатывание пишется в лог.
	std::atomic<int64_t> g_cooldown_until{0};
	constexpr int64_t BP_COOLDOWN_MS = 60000;
	bool InCooldown()
	{
		return GetTickCount64() < g_cooldown_until.load(std::memory_order_relaxed);
	}
	int64_t CooldownLeft()
	{
		const int64_t left = g_cooldown_until.load(std::memory_order_relaxed) - GetTickCount64();
		return left > 0 ? left / 1000 : 0;
	}
	void CooldownStart(const char* why)
	{
		g_cooldown_until.store(GetTickCount64() + BP_COOLDOWN_MS, std::memory_order_relaxed);
		LogLine(S("cooldown: пауза {} с после '{}' (страховка от краша слота D)", BP_COOLDOWN_MS / 1000, why));
	}
	bool CooldownGuard(const char* what)
	{
		if (!InCooldown())
			return false;
		LogLine(S("{}: отказ - пауза после сэмплер-окна не кончилась ({} с)", what, CooldownLeft()));
		return true;
	}
''')

src = insert_before('	// ------------------------------------------------- bptrace (ARCH.md 3.5)', COOLDOWN, src)

# ---------------------------------------- 2. инициализация слотов + частота QPC
INIT = blk('''	// Инициализация структур bptrace (слоты фиксированного размера, частота QPC).
	void BpInit()
	{
		if (g_bp_slotv.empty())
			g_bp_slotv.resize(BP_MAX_SLOTS);
		LARGE_INTEGER freq;
		if (QueryPerformanceFrequency(&freq) && freq.QuadPart > 0)
			g_bp_qpc_freq = freq.QuadPart;
		g_bp_win_start.store(GetTickCount64(), std::memory_order_relaxed);
		LogLine(S("bptrace v2: слотов={} глубина={} QPC={} Гц", BP_MAX_SLOTS, BP_MAX_DEPTH,
			g_bp_qpc_freq));
	}
''')

src = insert_before('	// ------------------------------------------------- bptrace (ARCH.md 3.5)', INIT, src)

# ---------------------------------------- 3. пауза после WriteResults
src = insert_after(blk('''			wait_path));'''), blk('''
		CooldownStart("окно сэмплирования");'''), src)

# ---------------------------------------- 4. проверки паузы в командах измерения
src = insert_after('''	void CmdWindow(RCONClientConnection*, RCONPacket* packet, UWorld*)
	{
''', blk('''		if (CooldownGuard("window"))
			return;
'''), src)

src = insert_after('''	void CmdPerf(RCONClientConnection*, RCONPacket* packet, UWorld*)
	{
''', blk('''		if (CooldownGuard("perf"))
			return;
'''), src)

src = insert_after('''	void CmdOverlaps(RCONClientConnection*, RCONPacket* packet, UWorld*)
	{
''', blk('''		if (CooldownGuard("overlaps"))
			return;
'''), src)

src = insert_after('''	void CmdStart(RCONClientConnection*, RCONPacket* packet, UWorld*)
	{
''', blk('''		if (CooldownGuard("start"))
			return;
'''), src)

# ---------------------------------------- 5. дамп флагов UFunction (подготовка П4)
FNFLAGS = blk('''	// Дамп флагов UFunction: есть ли return/out-параметры.
	// Основание безопасности для троттлинга (П4): функцию можно пропускать
	// только если она ничего не возвращает и не пишет out-параметры.
	// Смещения (сборка v361, подтверждено Ghidra):
	//   UStruct+0x38 = цепочка свойств (PropertyLink),
	//   FProperty+0x28 = Next, FProperty+0x38 = PropertyFlags (uint32),
	//   бит 0x80 = Parm, 0x100 = OutParm, 0x400 = ReturnParm.
	constexpr uint32_t USTRUCT_PROPS_OFFSET = 0x38;
	constexpr uint32_t FPROP_NEXT_OFFSET = 0x28;
	constexpr uint32_t FPROP_FLAGS_OFFSET = 0x38;
	constexpr uint32_t FPROP_PARM = 0x80;
	constexpr uint32_t FPROP_OUTPARM = 0x100;
	constexpr uint32_t FPROP_RETURNPARM = 0x400;
	void CmdFnFlags(RCONClientConnection*, RCONPacket* packet, UWorld*)
	{
		const std::string body = packet ? packet->Body.ToString() : "";
		std::string needle = body;
		const size_t sp = needle.find_last_of(' ');
		if (sp != std::string::npos)
			needle = needle.substr(sp + 1);
		UClass* fn_class = NativeCall<UClass*>(nullptr, "UFunction.StaticClass");
		if (!fn_class)
		{
			LogLine("fnflags: UFunction.StaticClass не разрешился");
			return;
		}
		TArray<UObject*> fns;
		Globals::GetObjectsOfClass(fn_class, &fns, true, EObjectFlags::RF_Transient);
		int32_t shown = 0;
		for (int32_t i = 0; i < fns.Num(); ++i)
		{
			void* fn = fns[i];
			if (!fn)
				continue;
			std::string nm;
			if (!BpNameOfUFunction(fn, nm))
				continue;
			if (!needle.empty() && nm.find(needle) == std::string::npos)
				continue;
			void** func_slot = reinterpret_cast<void**>(reinterpret_cast<uint8_t*>(fn) + UFUNCTION_FUNC_OFFSET);
			const bool script = (*func_slot == g_bp_orig_processinternal);
			int32_t parms = 0;
			int32_t outs = 0;
			int32_t rets = 0;
			void* prop = *reinterpret_cast<void**>(reinterpret_cast<uint8_t*>(fn) + USTRUCT_PROPS_OFFSET);
			int guard = 0;
			while (prop && guard++ < 256)
			{
				const uint32_t flags = *reinterpret_cast<uint32_t*>(reinterpret_cast<uint8_t*>(prop) + FPROP_FLAGS_OFFSET);
				if (flags & FPROP_PARM)
					++parms;
				if (flags & FPROP_OUTPARM)
					++outs;
				if (flags & FPROP_RETURNPARM)
					++rets;
				prop = *reinterpret_cast<void**>(reinterpret_cast<uint8_t*>(prop) + FPROP_NEXT_OFFSET);
			}
			LogLine(S("fnflags: {} script={} parms={} out={} return={} {}", nm, script, parms, outs, rets,
				(outs == 0 && rets == 0) ? "БЕЗОПАСНО-для-троттлинга" : "ЗАПРЕЩЕНО-для-троттлинга"));
			if (++shown >= 40)
				break;
		}
		LogLine(S("fnflags: показано {}", shown));
	}
''')

src = insert_before('	// ------------------------------------------------- census overlap-событий', FNFLAGS, src)

# ---------------------------------------- 6. регистрация команд
src = insert_after('''	cmds.AddRconCommand("TickProf.bptrace.report", [](RCONClientConnection* c, RCONPacket* p, UWorld* w) { CmdBpTraceReport(c, p, w); });''',
                    blk('''	cmds.AddRconCommand("TickProf.bptrace.reset", [](RCONClientConnection* c, RCONPacket* p, UWorld* w) { CmdBpTraceReset(c, p, w); });
	cmds.AddRconCommand("TickProf.bptrace.caller", [](RCONClientConnection* c, RCONPacket* p, UWorld* w) { CmdBpTraceCaller(c, p, w); });
	cmds.AddRconCommand("TickProf.fnflags", [](RCONClientConnection* c, RCONPacket* p, UWorld* w) { CmdFnFlags(c, p, w); });'''), src)

# ---------------------------------------- 7. вызов BpInit в Plugin_Init
src = insert_after('''	LogLine(S("loaded (Plugin_Init)", PLUGIN_NAME));''', blk('''	BpInit();'''), src)

io.open(CPP, 'w', encoding='utf-8', newline='').write(src)
print('П5 + инициализация + fnflags + команды добавлены')

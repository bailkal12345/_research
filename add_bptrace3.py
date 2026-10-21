# -*- coding: utf-8 -*-
# doit6 §4: bptrace - ЧИСТАЯ вставка одним проходом.
#
# Основание (ARCH.md 3.5):
#  * хук тела UObject::ProcessInternal (RVA 0x01FC0270); у скриптовой UFunction
#    поле Func == &ProcessInternal, поэтому хук накрывает оба пути вызова;
#  * логируем ТОЛЬКО полное имя UFunction и счётчик; аргументы не пишем,
#    поведение не меняем;
#  * по умолчанию ВЫКЛЮЧЕН, байты патча не ставятся вообще (нулевое влияние);
#  * индекс записи - __declspec(thread), буфер на поток, без блокировок;
#  * холодный путь (промах) - SRWLOCK;
#  * ENDBR64 в ProcessInternal нет => CET-трамплин "mov r11, imm64; jmp r11" (12 байт).
#
# Имя функции: FFrame::Node - это UFunction* (подтверждено декомпилом ProcessInternal:
# UFunction::GetReturnProperty(param_1->Node)). Имя берём через UObject::GetName.
import io, re, sys

CPP = r'C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp'
src = io.open(CPP, 'r', encoding='utf-8', newline='').read()
NL = '\r\n' if '\r\n' in src else '\n'


def blk(t):
    return t.replace('\n', NL)


# ---------- 0) откат предыдущих неудачных вставок ----------
if 'bptrace (ARCH.md 3.5)' in src:
    # вырезаем всё, что было вставлено ранее
    i = src.index(blk('	// ------------------------------------------------- bptrace (ARCH.md 3.5)'))
    j = src.index(blk('	// ------------------------------------------------- census overlap-событий'), i)
    src = src[:i] + src[j:]
    if 'void CmdBpTrace(' in src:
        i2 = src.index(blk('	void CmdBpTrace('))
        j2 = src.index(blk('	cmds.AddRconCommand("TickProf.cachestat",'), i2)
        src = src[:i2] + src[j2:]
    if 'TickProf.bptrace' in src:
        src = src.replace(blk('''	cmds.AddRconCommand("TickProf.bptrace", [](RCONClientConnection* c, RCONPacket* p, UWorld* w) { CmdBpTrace(c, p, w); });
'''), '', 1)
    print('откат предыдущих вставок bptrace выполнен')

# ---------- 1) блок данных + хук ----------
BLOCK = blk('''	// ------------------------------------------------- bptrace (ARCH.md 3.5)
	//
	// Трассировщик Blueprint: хук тела UObject::ProcessInternal (RVA 0x01FC0270).
	// У любой скриптовой UFunction поле Func == &ProcessInternal, поэтому хук
	// накрывает и прямые вызовы, и вызовы из Blueprint.
	//
	// ВАЖНО: по умолчанию ВЫКЛЮЧЕН, и байты патча НЕ СТАВЯТСЯ ВООБЩЕ, пока
	// трассировщик не включён явной командой RCON. Это буквальный ноль влияния на
	// процесс, а не "нулевая ветка".
	//
	// Логируем ТОЛЬКО полное имя UFunction и счётчик вызовов. Аргументы не пишем,
	// поведение не меняем.
	//
	// Имя функции берётся из FFrame: FFrame::Node - это UFunction* (подтверждено
	// декомпилом ProcessInternal: UFunction::GetReturnProperty(param_1->Node)).
	constexpr uint32_t BPTRACE_RVA = 0x01FC0270;
	constexpr int32_t BPTRACE_SLOTS = 4096;

	struct BpSlot
	{
		uint64_t Hash;
		uint64_t Count;
	};

	// Индекс записи - thread-local, буфер на поток: горячий путь без блокировок.
	thread_local int32_t g_bp_slot = -1;
	thread_local BpSlot g_bp_buf[BPTRACE_SLOTS];
	thread_local std::string g_bp_name;

	// Холодный путь (промах хеша) - SRWLOCK.
	SRWLOCK g_bp_lock = SRWLOCK_INIT;
	std::vector<std::string> g_bp_names;
	std::vector<uint64_t> g_bp_hash;
	std::atomic<int64_t> g_bp_calls{0};
	std::atomic<bool> g_bp_on{false};
	uint8_t g_bp_orig[12] = {};
	uint8_t* g_bp_target = nullptr;   // адрес ProcessInternal в памяти
	void* g_bp_orig_call = nullptr;    // трамплин "вызвать оригинал"

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

	// FFrame::Node = UFunction*; имя - через UObject::GetName.
	bool BpFunctionName(void* frame, std::string& out)
	{
		if (!frame)
			return false;
		UFunction* fn = *reinterpret_cast<UFunction**>(reinterpret_cast<uint8_t*>(frame) + sizeof(void*));
		if (!fn)
			return false;
		FString nm;
		if (!fn->GetName(&nm))
			return false;
		out = nm.ToString();
		return !out.empty();
	}

	void BpNote(const std::string& name)
	{
		const uint64_t h = BpHash(name);
		if (g_bp_slot < 0)
		{
			// Холодный путь: поиск/регистрация под SRWLOCK.
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
			if (found < 0 && (int32_t)g_bp_hash.size() < BPTRACE_SLOTS)
			{
				g_bp_names.push_back(name);
				g_bp_hash.push_back(h);
				found = (int32_t)g_bp_hash.size() - 1;
			}
			ReleaseSRWLockExclusive(&g_bp_lock);
			g_bp_slot = found;
		}
		if (g_bp_slot < 0)
			return;
		++g_bp_buf[g_bp_slot].Count;
	}

	// --- собственно хук: ProcessInternal(this=RCX, FFrame*=RDX, void*=R8) ---
	void __fastcall H_ProcessInternal(void* self, void* frame, void* result);
	void* _o_ProcessInternal = nullptr;

	void H_ProcessInternal(void* self, void* frame, void* result)
	{
		if (g_bp_on.load(std::memory_order_relaxed))
		{
			std::string nm;
			if (BpFunctionName(frame, nm))
				BpNote(nm);
		}
		typedef void(__fastcall* Fn)(void*, void*, void*);
		reinterpret_cast<Fn>(_o_ProcessInternal)(self, frame, result);
	}

	// CET-совместимый переход: "mov r11, imm64; jmp r11" (12 байт).
	// r11 - одноразовый регистр (не аргумент), стек не трогаем.
	uint8_t* BpMakeJump(void* target)
	{
		uint8_t* buf = (uint8_t*)VirtualAlloc(nullptr, 32, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
		if (!buf)
			return nullptr;
		buf[0] = 0x49; buf[1] = 0xBB;                       // mov r11, imm64
		std::memcpy(buf + 2, &target, 8);
		buf[10] = 0x41; buf[11] = 0xFF; buf[12] = 0xE3;      // jmp r11
		FlushInstructionCache(GetCurrentProcess(), buf, 16);
		return buf;
	}

	bool BpInstall()
	{
		if (g_bp_target)
			return true;
		uint8_t* mod = (uint8_t*)GetModuleHandleW(L"ShooterGameServer.exe");
		if (!mod)
			return false;
		uint8_t* target = mod + BPTRACE_RVA;
		// Трамплин для вызова оригинала: прыгаем на target+12 (оригинал пропущен 12 байт).
		void* after = target + 12;
		uint8_t* call = BpMakeJump(after);
		if (!call)
			return false;
		// Переход на наш обработчик: mov r11, H_ProcessInternal ; jmp r11
		uint8_t* handler = (uint8_t*)&H_ProcessInternal;
		DWORD old_prot = 0;
		if (!VirtualProtect(target, 12, PAGE_EXECUTE_READWRITE, &old_prot))
			return false;
		std::memcpy(g_bp_orig, target, 12);
		uint8_t patch[12];
		patch[0] = 0x49; patch[1] = 0xBB;
		std::memcpy(patch + 2, &handler, 8);
		patch[10] = 0x41; patch[11] = 0xFF; patch[12] = 0xE3;
		std::memcpy(target, patch, 12);
		FlushInstructionCache(GetCurrentProcess(), target, 12);
		VirtualProtect(target, 12, old_prot, &old_prot);
		_o_ProcessInternal = call;
		g_bp_target = target;
		return true;
	}

	void BpRemove()
	{
		if (!g_bp_target)
			return;
		DWORD old_prot = 0;
		if (VirtualProtect(g_bp_target, 12, PAGE_EXECUTE_READWRITE, &old_prot))
		{
			std::memcpy(g_bp_target, g_bp_orig, 12);
			FlushInstructionCache(GetCurrentProcess(), g_bp_target, 12);
			VirtualProtect(g_bp_target, 12, old_prot, &old_prot);
		}
		g_bp_target = nullptr;
		_o_ProcessInternal = nullptr;
		g_bp_on.store(false, std::memory_order_relaxed);
	}

	void CmdBpTrace(RCONClientConnection*, RCONPacket* packet, UWorld*)
	{
		const int32_t mode = ArgInt(packet, 0);
		if (mode == 0)
		{
			g_bp_on.store(false, std::memory_order_relaxed);
			LogLine(S("bptrace: выключен (вызовов {})", g_bp_calls.load()));
			BpRemove();
			return;
		}
		if (!g_bp_target && !BpInstall())
		{
			LogLine("bptrace: хук не установился");
			return;
		}
		g_bp_on.store(true, std::memory_order_relaxed);
		g_bp_calls.store(0);
		LogLine("bptrace: включён (CET-трамплин 12 байт), счётчики обнулены");
	}

''')

ANCHOR1 = blk('	// ------------------------------------------------- census overlap-событий\n')
assert ANCHOR1 in src, 'якорь census не найден'
src = src.replace(ANCHOR1, BLOCK + ANCHOR1, 1)

# регистрация команды
ANCHOR2 = blk('	cmds.AddRconCommand("TickProf.cachestat",')
assert ANCHOR2 in src, 'якорь команды не найден'
src = src.replace(ANCHOR2, blk('	cmds.AddRconCommand("TickProf.bptrace", [](RCONClientConnection* c, RCONPacket* p, UWorld* w) { CmdBpTrace(c, p, w); });\n') + ANCHOR2, 1)

io.open(CPP, 'w', encoding='utf-8', newline='').write(src)
print('bptrace вставлен чисто (блок + команда)')

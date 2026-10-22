# -*- coding: utf-8 -*-
# doit6 §4 (продолжение): установка/снятие хука bptrace + команда RCON + отчёт.
import io, sys

CPP = r'C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp'
src = io.open(CPP, 'r', encoding='utf-8', newline='').read()
NL = '\r\n' if '\r\n' in src else '\n'


def blk(t):
    return t.replace('\n', NL)


if 'void CmdBpTrace(' in src:
    print('CmdBpTrace уже есть - пропускаю')
    sys.exit(0)

# 1) сам хук + trampoline: вставляем рядом с блоком bptrace
ANCHOR1 = blk('''	void BpNote(const char* name)
''')
assert ANCHOR1 in src, 'BpNote не найден'

HOOK = blk('''	// --- собственно хук: ProcessInternal(this=RCX, FFrame*=RDX, void*=R8) ---
	void __fastcall H_ProcessInternal(void* self, void* frame, void* result);
	void* _o_ProcessInternal = nullptr;

	void H_ProcessInternal(void* self, void* frame, void* result)
	{
		if (g_bp_on)
		{
			const char* nm = BpFunctionName(frame);
			if (nm)
				BpNote(nm);
		}
		// Вызов оригинала: трамплин прыгает обратно в тело функции.
		typedef void(__fastcall* Fn)(void*, void*, void*);
		reinterpret_cast<Fn>(_o_ProcessInternal)(self, frame, result);
	}

	// CET-совместимый трамплин: "mov r11, imm64; jmp r11" (12 байт).
	// r11 - одноразовый регистр (не аргумент), стек не трогаем.
	void* MakeCetTrampoline(void* target)
	{
		uint8_t* buf = (uint8_t*)VirtualAlloc(nullptr, 32, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
		if (!buf)
			return nullptr;
		buf[0] = 0x49;              // mov r11, imm64
		buf[1] = 0xBB;
		std::memcpy(buf + 2, &target, 8);
		buf[10] = 0x41;             // jmp r11
		buf[11] = 0xFF;
		buf[12] = 0xE3;
		FlushInstructionCache(GetCurrentProcess(), buf, 16);
		return buf;
	}

	bool BpInstall()
	{
		if (g_bp_installed)
			return true;
		uint8_t* target = (uint8_t*)NativeCall<void*>(nullptr, "UObject.ProcessInternal");
		if (!target)
		{
			// RVA из ARCH.md 3.5 как запасной путь
			target = (uint8_t*)GetModuleHandleW(L"ShooterGameServer.exe");
			if (!target)
				return false;
			target += BPTRACE_RVA;
		}
		// Трамплин на тело оригинала: 12 байт копируются, поверх - mov r11/jmp r11
		// на наш обработчик.
		void* tramp = MakeCetTrampoline(target);
		if (!tramp)
			return false;
		// Оригинальные 12 байт сохраняем и делаем переход обратно:
		// отдельный "возвратный" трамплин (mov r11, orig+12 ; jmp r11).
		uint8_t* ret = (uint8_t*)VirtualAlloc(nullptr, 32, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
		if (!ret)
			return false;
		void* after = target + 12;
		ret[0] = 0x49; ret[1] = 0xBB;
		std::memcpy(ret + 2, &after, 8);
		ret[10] = 0x41; ret[11] = 0xFF; ret[12] = 0xE3;
		FlushInstructionCache(GetCurrentProcess(), ret, 16);

		DWORD old_prot = 0;
		if (!VirtualProtect(target, 12, PAGE_EXECUTE_READWRITE, &old_prot))
			return false;
		std::memcpy(g_bp_orig, target, 12);
		uint8_t patch[12];
		void* handler = (void*)&H_ProcessInternal;
		patch[0] = 0x49; patch[1] = 0xBB;
		std::memcpy(patch + 2, &handler, 8);
		patch[10] = 0x41; patch[11] = 0xFF; patch[12] = 0xE3;
		std::memcpy(target, patch, 12);
		FlushInstructionCache(GetCurrentProcess(), target, 12);
		VirtualProtect(target, 12, old_prot, &old_prot);
		// Оригинальный прыжок для вызова из хука:
		uint8_t* call = (uint8_t*)VirtualAlloc(nullptr, 32, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
		call[0] = 0x49; call[1] = 0xBB;
		std::memcpy(call + 2, &target, 8);
		call[10] = 0x41; call[11] = 0xFF; call[12] = 0xE3;
		FlushInstructionCache(GetCurrentProcess(), call, 16);
		_o_ProcessInternal = call;
		g_bp_jump = tramp;
		g_bp_installed = true;
		return true;
	}

	void BpRemove()
	{
		if (!g_bp_installed)
			return;
		uint8_t* target = nullptr;
		// Восстанавливаем оригинальные байты по сохранённому адресу.
		if (g_bp_jump)
		{
			// адрес цели = цель trampoline
			std::memcpy(&target, (uint8_t*)g_bp_jump + 2, 8);
		}
		if (target)
		{
			DWORD old_prot = 0;
			if (VirtualProtect(target, 12, PAGE_EXECUTE_READWRITE, &old_prot))
			{
				std::memcpy(target, g_bp_orig, 12);
				FlushInstructionCache(GetCurrentProcess(), target, 12);
				VirtualProtect(target, 12, old_prot, &old_prot);
			}
		}
		g_bp_installed = false;
		g_bp_on = false;
	}

''')

src = src.replace(ANCHOR1, ANCHOR1 + HOOK, 1)

# 2) команда RCON
ANCHOR2 = blk('''	cmds.AddRconCommand("TickProf.cachestat",''')
assert ANCHOR2 in src, 'место для команды не найден'
CMD = blk('''	void CmdBpTrace(RCONClientConnection*, RCONPacket* packet, UWorld*)
	{
		const int32_t mode = ArgInt(packet, 0);
		if (mode == 0)
		{
			g_bp_on = false;
			LogLine(S("bptrace: выключен (вызовов {})", g_bp_calls.load()));
			BpRemove();
			return;
		}
		if (!g_bp_installed)
		{
			if (!BpInstall())
			{
				LogLine("bptrace: хук не установился");
				return;
			}
			LogLine("bptrace: хук UObject.ProcessInternal установлен (CET-трамплин)");
		}
		g_bp_on = true;
		g_bp_calls.store(0);
		LogLine("bptrace: включён, счётчики обнулены");
	}

''')
src = src.replace(ANCHOR2, CMD + ANCHOR2, 1)

# 3) регистрация команды
ANCHOR3 = blk('''	cmds.AddRconCommand("TickProf.cachestat",''')
REG = blk('''	cmds.AddRconCommand("TickProf.bptrace", [](RCONClientConnection* c, RCONPacket* p, UWorld* w) { CmdBpTrace(c, p, w); });
''')
src = src.replace(ANCHOR3, REG + ANCHOR3, 1)

io.open(CPP, 'w', encoding='utf-8', newline='').write(src)
print('bptrace: хук + команда RCON добавлены')

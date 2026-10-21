# -*- coding: utf-8 -*-
# doit6 §4 (исправление 2): корректный bptrace-трамплин.
#
# ЧТО БЫЛО НЕ ТАК И ПОЧЕМУ ПАДАЛО:
#   тест 1: патч 12 байт, вызов оригинала прыгал на target+12 =>
#           пролог (PUSH RBX/RSI/RDI; SUB RSP,0x80) НЕ выполнялся => разрыв стека.
#   тест 2: патч 18 байт, в трамплин копировались 18 байт пролога, включая
#           RIP-относительную инструкцию "MOV RAX,[0x1448AFB30]" => при переносе
#           копии её RIP-база меняется => читается мусор => ломается security cookie.
#
# КОРРЕКТНЫЙ ПОДХОД:
#   смещаем ТОЛЬКО 11 байт пролога: PUSH RBX(2) PUSH RSI(1) PUSH RDI(1)
#   SUB RSP,0x80(7) = 11 байт. Ни одна из этих инструкций не RIP-относительна,
#   поэтому их безопасно копировать в трамплин. Следующая инструкция
#   (MOV RAX,[0x1448AFB30]) остаётся на месте и исполняется по своему RIP.
#   Патч на месте: 5-байтный относительный jmp (E9) + 6 NOP = 11 байт.
#   Трамплин: [ENDBR64][11 скопированных байт][mov r11,target+11; jmp r11].
#   Слот под трамплин выделяется рядом с целью (в пределах +-2 ГБ), чтобы jmp был
#   относительным 32-битным.
#   CET/IBT: наш обработчик начинается с ENDBR64; вызов оригинала - mov r11/call r11
#   на трамплин, который тоже начинается с ENDBR64.
import io, sys

CPP = r'C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp'
src = io.open(CPP, 'r', encoding='utf-8', newline='').read()
NL = '\r\n' if '\r\n' in src else '\n'


def blk(t):
    return t.replace('\n', NL)


start = src.index(blk('	// Размер перекрываемого блока ProcessInternal'))
end = src.index(blk('	void CmdBpTrace('), start)

NEW = blk('''	// Смещаемый блок ProcessInternal: только ПРОЛОГ, 11 байт:
	//   PUSH RBX(2) PUSH RSI(1) PUSH RDI(1) SUB RSP,0x80(7)
	// Ни одна из них не RIP-относительна, поэтому безопасно копировать.
	// Следующая за ними инструкция (MOV RAX,[0x1448AFB30]) остаётся на месте.
	constexpr size_t BPTRACE_PATCH = 11;

	// Трамплин оригинала: [ENDBR64][скопированный пролог][jmp r11 -> target+11].
	uint8_t* BpMakeTrampoline(const uint8_t* orig, size_t len, void** after_out)
	{
		uint8_t* buf = (uint8_t*)VirtualAlloc(nullptr, len + 48, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
		if (!buf)
			return nullptr;
		size_t o = 0;
		buf[o++] = 0xF3; buf[o++] = 0x0F; buf[o++] = 0x1E; buf[o++] = 0xFA;  // endbr64
		std::memcpy(buf + o, orig, len);
		o += len;
		void* after = (void*)(orig + len);
		buf[o++] = 0x49; buf[o++] = 0xBB;                     // mov r11, imm64
		std::memcpy(buf + o, &after, 8);
		o += 8;
		buf[o++] = 0x41; buf[o++] = 0xFF; buf[o++] = 0xE3;     // jmp r11
		FlushInstructionCache(GetCurrentProcess(), buf, o);
		if (after_out)
			*after_out = buf;
		return buf;
	}

	// Обработчик: [ENDBR64] + переход на тело хука.
	// Ставится вблизи цели, чтобы 5-байтный относительный jmp был в пределах +-2 ГБ.
	uint8_t* BpAllocNear(void* target, size_t need)
	{
		SYSTEM_INFO si;
		GetSystemInfo(&si);
		const uintptr_t gran = si.dwAllocationGranularity;
		const uintptr_t t = (uintptr_t)target;
		for (uintptr_t off = 0x10000; off < 0x70000000; off += gran)
		{
			for (int dir = 0; dir < 2; ++dir)
			{
				const uintptr_t a = (dir == 0) ? (t + off) : (t - off);
				uint8_t* p = (uint8_t*)VirtualAlloc((void*)(a & ~(gran - 1)), need,
					MEM_COMMIT | MEM_RESERVE | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
				if (p)
					return p;
			}
		}
		return nullptr;
	}

	bool BpInstall()
	{
		if (g_bp_target)
			return true;
		uint8_t* mod = (uint8_t*)GetModuleHandleW(L"ShooterGameServer.exe");
		if (!mod)
			return false;
		uint8_t* target = mod + BPTRACE_RVA;
		// Трамплин: пролог + jmp на target+11.
		uint8_t* tramp = BpMakeTrampoline(target, BPTRACE_PATCH, nullptr);
		if (!tramp)
			return false;
		// Обработчик ставим рядом с целью (для относительного jmp).
		uint8_t* stub = BpAllocNear(target, 64);
		if (!stub)
			return false;
		size_t o = 0;
		stub[o++] = 0xF3; stub[o++] = 0x0F; stub[o++] = 0x1E; stub[o++] = 0xFA;  // endbr64
		// jmp на H_ProcessInternal (абсолютный, через r11)
		void* handler = (void*)&H_ProcessInternal;
		stub[o++] = 0x49; stub[o++] = 0xBB;
		std::memcpy(stub + o, &handler, 8);
		o += 8;
		stub[o++] = 0x41; stub[o++] = 0xFF; stub[o++] = 0xE3;   // jmp r11
		FlushInstructionCache(GetCurrentProcess(), stub, o);

		// Патчим цель: 5-байтный относительный jmp на stub + NOP-ы до 11 байт.
		const int32_t rel = (int32_t)((int64_t)stub - (int64_t)(target + 5));
		DWORD old_prot = 0;
		if (!VirtualProtect(target, BPTRACE_PATCH, PAGE_EXECUTE_READWRITE, &old_prot))
			return false;
		std::memcpy(g_bp_orig, target, BPTRACE_PATCH);
		target[0] = 0xE9;                                       // jmp rel32
		std::memcpy(target + 1, &rel, 4);
		for (size_t i = 5; i < BPTRACE_PATCH; ++i)
			target[i] = 0x90;                                    // nop
		FlushInstructionCache(GetCurrentProcess(), target, BPTRACE_PATCH);
		VirtualProtect(target, BPTRACE_PATCH, old_prot, &old_prot);
		_o_ProcessInternal = tramp;
		g_bp_target = target;
		g_bp_stub = stub;
		return true;
	}

	void BpRemove()
	{
		if (!g_bp_target)
			return;
		DWORD old_prot = 0;
		if (VirtualProtect(g_bp_target, BPTRACE_PATCH, PAGE_EXECUTE_READWRITE, &old_prot))
		{
			std::memcpy(g_bp_target, g_bp_orig, BPTRACE_PATCH);
			FlushInstructionCache(GetCurrentProcess(), g_bp_target, BPTRACE_PATCH);
			VirtualProtect(g_bp_target, BPTRACE_PATCH, old_prot, &old_prot);
		}
		g_bp_target = nullptr;
		_o_ProcessInternal = nullptr;
		g_bp_on.store(false, std::memory_order_relaxed);
	}

''')

src = src[:start] + NEW + src[end:]

# объявление g_bp_stub
if 'uint8_t* g_bp_stub' not in src:
    src = src.replace(blk('	uint8_t* g_bp_target = nullptr;   // адрес ProcessInternal в памяти'),
                      blk('	uint8_t* g_bp_target = nullptr;   // адрес ProcessInternal в памяти\n'
                          '	uint8_t* g_bp_stub = nullptr;     // обработчик рядом с целью'), 1)

# хук: вызов оригинала - mov r11,tramp ; call r11 (трамплин с ENDBR64)
OLD_CALL = blk('''		typedef void(__fastcall* Fn)(void*, void*, void*);
		reinterpret_cast<Fn>(_o_ProcessInternal)(self, frame, result);''')
NEW_CALL = blk('''		// Вызов оригинала: mov r11, трамплин; call r11 (трамплин начинается с ENDBR64).
		typedef void(__fastcall* Fn)(void*, void*, void*);
		void* tramp = _o_ProcessInternal;
		asm volatile("mov r11, %0\\n\\tcall r11" : : "r"(tramp) : "r11", "memory");
		(void)result;''')
if OLD_CALL in src:
    src = src.replace(OLD_CALL, NEW_CALL, 1)

io.open(CPP, 'w', encoding='utf-8', newline='').write(src)
print('bptrace: переписан на 11-байтовое смещение пролога + копирующий трамплин + ENDBR64')

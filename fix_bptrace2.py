# -*- coding: utf-8 -*-
# doit6 §4 (продолжение): исправление bptrace - патч 12 байт РАЗРЫВАЛ инструкцию.
#
# Найдено (Ghidra, /v361_ShooterGameServer.exe, ProcessInternal 0x141FC0270):
#   0x141FC0270  40 53           PUSH RBX            (2)
#   0x141FC0272  56              PUSH RSI            (1)
#   0x141FC0273  57              PUSH RDI            (1)
#   0x141FC0274  48 81 ec 80 00 00 00  SUB RSP,0x80   (7)
#   0x141FC027B  48 8b 05 ...    MOV RAX,[0x1448AFB30] (7)  <- 12 байт режут этот MOV
# Итого: 12-байтовый патч попадал внутрь 7-байтовой инструкции MOV => падение.
#
# Исправление: патчим 19 байт (4 инструкции целиком: 2+1+1+7 = 11 байт, затем
# MOV RAX,[...] целиком: 11+7 = 18, добираем 19 с запасом - нет, надо ровно по
# границе инструкций). Считаем: 2+1+1+7+7 = 18 байт - это 5 целых инструкций.
# Значит патчим 18 байт, а в "call-трамплин" возвращаем на target+18.
# Трамплин "вызова оригинала" копирует оригинальные 18 байт в исполняемую область
# и заканчивается jmp r11 на target+18.
import io, sys

CPP = r'C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp'
src = io.open(CPP, 'r', encoding='utf-8', newline='').read()
NL = '\r\n' if '\r\n' in src else '\n'


def blk(t):
    return t.replace('\n', NL)


# --- 1) заменяем BpInstall/BpRemove на корректную версию (копирование оригинала) ---
start = src.index(blk('	bool BpInstall()'))
end = src.index(blk('	void CmdBpTrace('), start)
old = src[start:end]

NEW = blk('''	// Размер перекрываемого блока ProcessInternal: 5 целых инструкций = 18 байт
	// (PUSH RBX; PUSH RSI; PUSH RDI; SUB RSP,0x80; MOV RAX,[0x1448AFB30]).
	// Патчить меньше нельзя - 12 байт разрезали 7-байтовую инструкцию MOV (падение).
	constexpr size_t BPTRACE_PATCH = 18;

	// Копирование оригинальных байтов в исполняемую область + jmp r11 обратно.
	uint8_t* BpMakeTrampoline(const uint8_t* orig, size_t len)
	{
		uint8_t* buf = (uint8_t*)VirtualAlloc(nullptr, len + 32, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
		if (!buf)
			return nullptr;
		std::memcpy(buf, orig, len);
		void* after = (void*)(orig + len);
		buf[len + 0] = 0x49; buf[len + 1] = 0xBB;          // mov r11, imm64
		std::memcpy(buf + len + 2, &after, 8);
		buf[len + 10] = 0x41; buf[len + 11] = 0xFF; buf[len + 12] = 0xE3;  // jmp r11
		FlushInstructionCache(GetCurrentProcess(), buf, len + 16);
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
		// Трамплин оригинала: копия перекрываемого блока + jmp на target+18.
		uint8_t* tramp = BpMakeTrampoline(target, BPTRACE_PATCH);
		if (!tramp)
			return false;
		// Переход на обработчик: mov r11, H_ProcessInternal ; jmp r11 (12 байт).
		uint8_t* handler = (uint8_t*)&H_ProcessInternal;
		DWORD old_prot = 0;
		if (!VirtualProtect(target, BPTRACE_PATCH, PAGE_EXECUTE_READWRITE, &old_prot))
			return false;
		std::memcpy(g_bp_orig, target, BPTRACE_PATCH);
		uint8_t patch[12];
		patch[0] = 0x49; patch[1] = 0xBB;
		std::memcpy(patch + 2, &handler, 8);
		patch[10] = 0x41; patch[11] = 0xFF; patch[12] = 0xE3;
		std::memcpy(target, patch, 12);
		// Остаток перекрытого блока (12..18) - NOP-ы, чтобы длина не поехала.
		for (size_t i = 12; i < BPTRACE_PATCH; ++i)
			target[i] = 0x90;
		FlushInstructionCache(GetCurrentProcess(), target, BPTRACE_PATCH);
		VirtualProtect(target, BPTRACE_PATCH, old_prot, &old_prot);
		_o_ProcessInternal = tramp;
		g_bp_target = target;
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

# --- 2) размер буфера оригинальных байт: 18 вместо 12 ---
src = src.replace(blk('	uint8_t g_bp_orig[12] = {};'), blk('	uint8_t g_bp_orig[32] = {};'), 1)

# --- 3) удаляем старый BpMakeJump (заменён на BpMakeTrampoline) ---
if '	uint8_t* BpMakeJump(void* target)' in src:
    i = src.index(blk('	uint8_t* BpMakeJump(void* target)'))
    j = src.index(blk('	bool BpInstall()'), i)
    src = src[:i] + src[j:]

io.open(CPP, 'w', encoding='utf-8', newline='').write(src)
print('bptrace: патч расширен до 18 байт (5 целых инструкций), добавлен копирующий трамплин')

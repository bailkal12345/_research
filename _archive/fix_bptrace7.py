# -*- coding: utf-8 -*-
# doit6 §4 (финальная схема): bptrace без изменения RSP и без правки cookie.
#
# ИТОГ РАЗБОРА ТРЁХ ПАДЕНИЙ/ЗАВИСАНИЙ:
#  1) патч 12 байт разрезал 7-байтовую инструкцию MOV RAX,[rip+..] -> падение;
#  2) копирование RIP-относительной инструкции в трамплин меняло её базу -> падение;
#  3) вызов оригинала менял RSP (call/+8 либо sub/add) -> security cookie оригинала
#     (XOR RAX,[0x1448AFB30],RSP) не сходился -> зависание.
#
# ФИНАЛЬНАЯ СХЕМА (всё через сгенерированный машинный код, x64 MSVC без inline asm):
#
#   [вызывающий]  call ProcessInternal        -> в стеке ret_вызывающего
#   [патч 11 B]   jmp rel32 -> stub           -> стек не изменён
#   [stub]         endbr64
#                  sub  rsp, 0x28              ; выравнивание + место под сохранение self
#                  mov  [rsp+0x20], rcx        ; сохранить self
#                  mov  rax, rdx
#                  mov  rcx, rax               ; аргумент helper'а = FFrame*
#                  mov  r11, BpCountHelper
#                  call r11                    ; ВЫЗОВ СЧЁТЧИКА (выравнивание ок)
#                  mov  rcx, [rsp+0x20]        ; вернуть self
#                  add  rsp, 0x28              ; RSP как был
#                  mov  r11, trampoline
#                  jmp  r11                    ; хвостовой переход, БЕЗ изменения RSP
#   [trampoline]   endbr64
#                  PUSH RBX; PUSH RSI; PUSH RDI; SUB RSP,0x80   ; ПРОЛОГ ОРИГИНАЛА
#                  mov r11, target+11
#                  jmp r11
#   [оригинал]    ...продолжение с target+11 ... epilogue: add rsp,0x80; pop x3; ret
#                  -> ret снимает ret_вызывающего (RSP в эпилоге идентичен штатному!)
#
# Инвариант: RSP при входе в оригинал (после пролога) ТОЧНО такой же, как при
# штатном вызове => cookie сходится => epilogue делает ret к вызывающему.
import io, sys

CPP = r'C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp'
src = io.open(CPP, 'r', encoding='utf-8', newline='').read()
NL = '\r\n' if '\r\n' in src else '\n'


def blk(t):
    return t.replace('\n', NL)


# ---- 1) заменяем блок установки/трамплина ----
start = src.index(blk('	// Смещаемый блок ProcessInternal: только ПРОЛОГ, 11 байт:'))
end = src.index(blk('	void CmdBpTrace('), start)

NEW = blk('''	// Смещаемый блок ProcessInternal: только ПРОЛОГ, 11 байт:
	//   PUSH RBX(2) PUSH RSI(1) PUSH RDI(1) SUB RSP,0x80(7)
	// Ни одна из них не RIP-относительна, поэтому безопасно копировать.
	// Следующая за ними инструкция (MOV RAX,[0x1448AFB30]) остаётся на месте.
	constexpr size_t BPTRACE_PATCH = 11;

	extern "C" void BpCountHelper(void* frame);

	// Трамплин оригинала: [endbr64][копия пролога][jmp r11 -> target+11].
	// Вызывается ЧЕРЕЗ ХВОСТОВОЙ ПЕРЕХОД (jmp), поэтому RSP не меняется.
	uint8_t* BpMakeTrampoline(const uint8_t* orig, size_t len)
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
		return buf;
	}

	// Стаб рядом с целью (для 5-байтного относительного jmp в патче).
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
					MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
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
		uint8_t* tramp = BpMakeTrampoline(target, BPTRACE_PATCH);
		if (!tramp)
			return false;
		uint8_t* stub = BpAllocNear(target, 64);
		if (!stub)
			return false;
		// Стаб: endbr64; sub rsp,0x28; mov [rsp+0x20],rcx; mov rax,rdx; mov rcx,rax;
		//        mov r11,helper; call r11; mov rcx,[rsp+0x20]; add rsp,0x28;
		//        mov r11,tramp; jmp r11
		{
			size_t o = 0;
			stub[o++] = 0xF3; stub[o++] = 0x0F; stub[o++] = 0x1E; stub[o++] = 0xFA;  // endbr64
			stub[o++] = 0x48; stub[o++] = 0x83; stub[o++] = 0xEC; stub[o++] = 0x28;  // sub rsp,0x28
			stub[o++] = 0x48; stub[o++] = 0x89; stub[o++] = 0x4C; stub[o++] = 0x24;  // mov [rsp+0x20],rcx
			stub[o++] = 0x24; stub[o++] = 0x20;
			stub[o++] = 0x48; stub[o++] = 0x89; stub[o++] = 0xC2;                 // mov rax,rdx
			stub[o++] = 0x48; stub[o++] = 0x89; stub[o++] = 0xC1;                 // mov rcx,rax
			void* helper = (void*)&BpCountHelper;
			stub[o++] = 0x49; stub[o++] = 0xBB;                                 // mov r11, imm64
			std::memcpy(stub + o, &helper, 8);
			o += 8;
			stub[o++] = 0x41; stub[o++] = 0xFF; stub[o++] = 0xD3;                 // call r11
			stub[o++] = 0x48; stub[o++] = 0x8B; stub[o++] = 0x4C; stub[o++] = 0x24;  // mov rcx,[rsp+0x20]
			stub[o++] = 0x24; stub[o++] = 0x20;
			stub[o++] = 0x48; stub[o++] = 0x83; stub[o++] = 0xC4; stub[o++] = 0x28;  // add rsp,0x28
			stub[o++] = 0x49; stub[o++] = 0xBB;                                 // mov r11, imm64
			std::memcpy(stub + o, &tramp, 8);
			o += 8;
			stub[o++] = 0x41; stub[o++] = 0xFF; stub[o++] = 0xE3;                 // jmp r11
			FlushInstructionCache(GetCurrentProcess(), stub, o);
		}
		// Патч цели: 5-байтный относительный jmp на стаб + NOP до 11 байт.
		const int32_t rel = (int32_t)((int64_t)stub - (int64_t)(target + 5));
		DWORD old_prot = 0;
		if (!VirtualProtect(target, BPTRACE_PATCH, PAGE_EXECUTE_READWRITE, &old_prot))
			return false;
		std::memcpy(g_bp_orig, target, BPTRACE_PATCH);
		target[0] = 0xE9;
		std::memcpy(target + 1, &rel, 4);
		for (size_t i = 5; i < BPTRACE_PATCH; ++i)
			target[i] = 0x90;
		FlushInstructionCache(GetCurrentProcess(), target, BPTRACE_PATCH);
		VirtualProtect(target, BPTRACE_PATCH, old_prot, &old_prot);
		_o_ProcessInternal = tramp;
		g_bp_trampoline = tramp;
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
		g_bp_trampoline = nullptr;
		g_bp_on.store(false, std::memory_order_relaxed);
	}

	// Счётчик вызовов: вызывается из стаба (машинный код), поэтому extern "C" и
	// без исключений наружу (исключение не должно пересекать хук).
	extern "C" void BpCountHelper(void* frame)
	{
		try
		{
			if (!g_bp_on.load(std::memory_order_relaxed))
				return;
			std::string nm;
			if (BpFunctionName(frame, nm))
				BpNote(nm);
		}
		catch (...)
		{
		}
	}

''')

src = src[:start] + NEW + src[end:]

# ---- 2) обработчик-обёртка больше не нужен: считает стаб, тело оригинала уходит
#        через трамплин (хвостовой jmp) - заменяем тело H_ProcessInternal ----
old_h = blk('''	void H_ProcessInternal(void* self, void* frame, void* result)
	{
		if (g_bp_on.load(std::memory_order_relaxed))
		{
			std::string nm;
			if (BpFunctionName(frame, nm))
				BpNote(nm);
		}
		// Вызов оригинала.
		//
		// КРИТИЧНО про RSP: оригинал вычисляет security cookie как
		// XOR RAX(=[0x1448AFB30]), RSP, где RSP - значение ПОСЛЕ пролога
		// (PUSH x3; SUB RSP,0x80). Трамплин выполняет ровно этот пролог и
		// прыгает на target+11, поэтому при входе в оригинал RSP должен быть
		// таким же, как при обычном вызове (call кладёт ret-адрес, PUSH x3 и
		// SUB RSP,0x80 - то же, что делает оригинал).
		//
		// Поэтому трамплин вызывается ОБЫЧНЫМ C++-вызовом функции-указателя:
		// call даёт на стеке ret-адрес (как и ожидает оригинал), а трамплин
		// выполняет PUSH RBX/RSI/RDI; SUB RSP,0x80; jmp target+11.
		// Оригинал завершается ret'ом по адресу, который положил CALL.
		typedef void(__fastcall* Fn)(void*, void*, void*);
		reinterpret_cast<Fn>(_o_ProcessInternal)(self, frame, result);
	}''')

new_h = blk('''	// Обработчик больше не вызывается как C++-функция: патч ведёт в стаб
	// (машинный код), который считает вызовы и уходит в трамплин хвостовым jmp.
	// Объявление оставлено, чтобы адрес обработчика был валидной точкой входа,
	// если патч будет переделан.
	void __fastcall H_ProcessInternal(void* self, void* frame, void* result);''')

if old_h in src:
    src = src.replace(old_h, new_h, 1)
else:
    print('ВНИМАНИЕ: тело H_ProcessInternal отличается от ожидаемого')
    i = src.find('void H_ProcessInternal')
    print(repr(src[i:i + 700]))

io.open(CPP, 'w', encoding='utf-8', newline='').write(src)
print('bptrace: финальная схема (стаб + хвостовой jmp) применена')

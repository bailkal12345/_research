# -*- coding: utf-8 -*-
# doit6 §4 (исправление 3): вызов оригинала без inline asm.
#
# x64 MSVC не поддерживает __asm. Вместо него генерируем машинный код вызова
# в RW-памяти: "mov r11, [rel_tramp]; call r11; ret" - тот же CET-совместимый
# способ, что и в трамплине, но без зависимости от поддержки asm компилятором.
import io, sys

CPP = r'C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp'
src = io.open(CPP, 'r', encoding='utf-8', newline='').read()
NL = '\r\n' if '\r\n' in src else '\n'


def blk(t):
    return t.replace('\n', NL)


OLD = blk('''		// Вызов оригинала: mov r11, трамплин; call r11 (трамплин начинается с ENDBR64).
		// Собрано отдельной naked-функцией: MSVC не поддерживает "asm volatile".
		BpCallOriginal(self, frame, result);
	}

	// Трамплин вызова оригинала (глобальный, чтобы naked-функция его видела).
	void* g_bp_call_tramp = nullptr;

	__declspec(naked) static void BpCallOriginal(void* self, void* frame, void* result)
	{
		// mov r11, [g_bp_call_tramp] ; call r11 ; ret
		__asm
		{
			mov r11, g_bp_call_tramp
			call r11
			ret
		}
	}''')

NEW = blk('''		// Вызов оригинала: mov r11, трамплин; call r11; ret.
		// Код генерируется в RW-память (x64 MSVC не поддерживает inline asm).
		// Регистры self/frame/result уже в RCX/RDX/R8 (не трогаем).
		if (g_bp_call_code)
		{
			typedef void(__fastcall* Fn)(void*, void*, void*);
			reinterpret_cast<Fn>(g_bp_call_code)(self, frame, result);
		}
	}''')

assert OLD in src, 'фрагмент вызова оригинала не найден'
src = src.replace(OLD, NEW, 1)

# объявления и генерация кода вызова
OLD_DECL = blk('''	void* _o_ProcessInternal = nullptr;''')
NEW_DECL = blk('''	void* _o_ProcessInternal = nullptr;    // трамплин оригинала (копия пролога)
	void* g_bp_call_code = nullptr;          // сгенерированный "mov r11,tramp; call r11; ret"''')
assert OLD_DECL in src, 'объявление _o_ProcessInternal не найдено'
src = src.replace(OLD_DECL, NEW_DECL, 1)

# генерация кода вызова в BpInstall
OLD_INSTALL = blk('''		_o_ProcessInternal = tramp;
		g_bp_target = target;
		g_bp_stub = stub;
		return true;''')
NEW_INSTALL = blk('''		// Генерируем код вызова оригинала: mov r11, <tramp>; call r11; ret.
		// Адрес трамплина кладём рядом, чтобы mov был rip-относительным.
		uint8_t* call_code = (uint8_t*)VirtualAlloc(nullptr, 32, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
		if (!call_code)
			return false;
		{
			size_t c = 0;
			call_code[c++] = 0x4C; call_code[c++] = 0x8B; call_code[c++] = 0x1D;  // mov r11, [rip+disp32]
			const int32_t d = (int32_t)((int64_t)tramp - (int64_t)(call_code + c + 4));
			std::memcpy(call_code + c, &d, 4);
			c += 4;
			call_code[c++] = 0x41; call_code[c++] = 0xFF; call_code[c++] = 0xD3;  // call r11
			call_code[c++] = 0xC3;                                             // ret
			FlushInstructionCache(GetCurrentProcess(), call_code, c);
		}
		_o_ProcessInternal = tramp;
		g_bp_call_code = call_code;
		g_bp_target = target;
		g_bp_stub = stub;
		return true;''')
assert OLD_INSTALL in src, 'конец BpInstall не найден'
src = src.replace(OLD_INSTALL, NEW_INSTALL, 1)

io.open(CPP, 'w', encoding='utf-8', newline='').write(src)
print('bptrace: вызов оригинала переведён на сгенерированный машинный код (без inline asm)')

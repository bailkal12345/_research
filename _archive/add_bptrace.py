# -*- coding: utf-8 -*-
# doit6 §4: bptrace по ARCH.md 3.5 - трассировщик Blueprint.
#
# Требования ARCH.md §3.5:
#  * хук тела UObject::ProcessInternal (RVA 0x01FC0270). Для скриптовой UFunction
#    поле Func == &ProcessInternal, поэтому хук накрывает оба пути вызова;
#  * логируем ТОЛЬКО полное имя UFunction и счётчик вызовов; аргументы не пишем,
#    поведение не меняем;
#  * ПО УМОЛЧАНИЮ ВЫКЛЮЧЕН, байты патча не ставить вообще (буквальный ноль влияния);
#  * индекс записи - __declspec(thread), буфер на поток, без блокировок в горячем пути;
#  * холодный путь (промах) - SRWLOCK;
#  * ENDBR64 в ProcessInternal отсутствует => CET-совместимый трамплин
#    "mov r11, imm64; jmp r11" (12 байт, стек не трогает).
#
# Ключевой факт (Ghidra, декомпил ProcessInternal):
#   FFrame->Node - это UFunction* (UFunction::GetReturnProperty(param_1->Node)).
#   Значит полное имя функции берётся прямо из FFrame, без поиска контекста.
import io, sys

CPP = r'C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp'
src = io.open(CPP, 'r', encoding='utf-8', newline='').read()
NL = '\r\n' if '\r\n' in src else '\n'


def blk(t):
    return t.replace('\n', NL)


if 'bptrace (ARCH.md 3.5)' in src:
    print('bptrace уже есть в исходнике - пропускаю')
    sys.exit(0)

ANCHOR = blk('''	// ------------------------------------------------- census overlap-событий
''')
assert ANCHOR in src, 'якорь вставки не найден'

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
	// Имя функции берётся из FFrame: FFrame::Node - это UFunction* (проверено
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

	// Холодный путь (промах хеша) - SRWLOCK.
	SRWLOCK g_bp_lock = SRWLOCK_INIT;
	std::vector<std::string> g_bp_names;
	std::vector<uint64_t> g_bp_hash;
	std::vector<uint64_t> g_bp_total_count;
	std::atomic<int64_t> g_bp_calls{0};
	bool g_bp_on = false;
	uint8_t g_bp_orig[12] = {};
	uint8_t* g_bp_jump = nullptr;   // mov r11,imm64 ; jmp r11

	uint64_t BpHash(const TCHAR* s)
	{
		uint64_t h = 1469598103934665603ULL;
		for (const TCHAR* p = s; p && *p; ++p)
		{
			h ^= (uint64_t)(uint32_t)*p;
			h *= 1099511628211ULL;
		}
		return h ? h : 1;
	}

	// FFrame: Node = UFunction*. Достаём полное имя.
	const char* BpFunctionName(void* frame)
	{
		if (!frame)
			return nullptr;
		UFunction* fn = *reinterpret_cast<UFunction**>(reinterpret_cast<uint8_t*>(frame) + sizeof(void*));
		if (!fn)
			return nullptr;
		// UFunction::GetName() -> FString
		FString nm;
		if (!fn->GetName(&nm))
			return nullptr;
		return *nm.ToString();
	}

	void BpNote(const char* name)
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
				g_bp_total_count.push_back(0);
				found = (int32_t)g_bp_hash.size() - 1;
			}
			ReleaseSRWLockExclusive(&g_bp_lock);
			g_bp_slot = found;
		}
		if (g_bp_slot < 0)
			return;
		++g_bp_buf[g_bp_slot].Count;
		++g_bp_buf[g_bp_slot].Hash;
	}

''')

src = src.replace(ANCHOR, BLOCK + ANCHOR, 1)
io.open(CPP, 'w', encoding='utf-8', newline='').write(src)
print('блок bptrace вставлен (%d символов)' % len(BLOCK))

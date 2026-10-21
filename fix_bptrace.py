# -*- coding: utf-8 -*-
# Починка вставки bptrace: 1) восстановить тело BpNote, 2) имя UFunction через
# UObject::GetName (доступно), 3) сдвинуть хук-блок ПОСЛЕ BpNote.
import io, sys

CPP = r'C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp'
src = io.open(CPP, 'r', encoding='utf-8', newline='').read()
NL = '\r\n' if '\r\n' in src else '\n'


def blk(t):
    return t.replace('\n', NL)


# --- 1) вырезаем хук-блок, вставленный внутрь BpNote ---
HOOK_START = blk('''	// --- собственно хук: ProcessInternal(this=RCX, FFrame*=RDX, void*=R8) ---
''')
assert HOOK_START in src, 'хук-блок не найден'
i = src.index(HOOK_START)
# конец хук-блока: строка "	void BpRemove()" + её тело до закрывающей скобки
j = src.index(blk('''	void BpRemove()
'''), i)
# найти конец тела BpRemove: следующая "	void " после j
k = src.index(blk('''	void '''), j + 10)
hook_block = src[i:k]
src = src[:i] + src[k:]

# --- 2) восстанавливаем тело BpNote (оно было разрезано) ---
BROKEN = blk('''	void BpNote(const char* name)
''')
assert BROKEN in src, 'BpNote не найден'
FIXED = blk('''	void BpNote(const char* name)
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
src = src.replace(BROKEN, FIXED, 1)

# --- 3) имя функции: UObject::GetName доступен, UFunction::GetName - нет ---
OLD_NAME = blk('''		// UFunction::GetName() -> FString
		FString nm;
		if (!fn->GetName(&nm))
			return nullptr;
		return *nm.ToString();''')
NEW_NAME = blk('''		// UFunction - это UObject: имя берём через UObject::GetName (доступен в ArkApi).
		FString nm;
		if (!fn->GetName(&nm))
			return nullptr;
		const std::string s = nm.ToString();
		return s.c_str();''')
assert OLD_NAME in src, 'фрагмент имени не найден'
src = src.replace(OLD_NAME, NEW_NAME, 1)

# возвращаем строковый буфер: имя должно жить дольше вызова
OLD_RET = blk('''		const std::string s = nm.ToString();
		return s.c_str();''')
NEW_RET = blk('''		g_bp_name_buf = nm.ToString();
		return g_bp_name_buf.c_str();''')
src = src.replace(OLD_RET, NEW_RET, 1)

# объявление буфера
OLD_DECL = blk('''	thread_local BpSlot g_bp_buf[BPTRACE_SLOTS];''')
NEW_DECL = blk('''	thread_local BpSlot g_bp_buf[BPTRACE_SLOTS];
	thread_local std::string g_bp_name_buf;''')
assert OLD_DECL in src, 'объявление буфера не найдено'
src = src.replace(OLD_DECL, NEW_DECL, 1)

# --- 4) вставляем хук-блок после тела BpNote ---
ANCHOR = blk('''	// ------------------------------------------------- census overlap-событий
''')
assert ANCHOR in src, 'якорь census не найден'
src = src.replace(ANCHOR, hook_block + ANCHOR, 1)

io.open(CPP, 'w', encoding='utf-8', newline='').write(src)
print('bptrace: структура исправлена (BpNote восстановлен, хук вынесен, имя через UObject::GetName)')

# -*- coding: utf-8 -*-
# Финальная чистка H_ProcessInternal: счётчик теперь делает стаб, тело функции
# не должно ни считать, ни вызывать оригинала (иначе рекурсия/двойной вызов).
import io

CPP = r'C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp'
s = io.open(CPP, 'r', encoding='utf-8', newline='').read()
NL = '\r\n' if '\r\n' in s else '\n'


def blk(t):
    return t.replace('\n', NL)


i = s.index(blk('	void H_ProcessInternal(void* self, void* frame, void* result)'))
j = s.index(blk('	// Смещаемый блок ProcessInternal: только ПРОЛОГ, 11 байт:'), i)

NEW = blk('''	// Обработчик не вызывается как C++-функция: патч ведёт в стаб (машинный
	// код), который считает вызовы и уходит в трамплин хвостовым jmp. Объявление
	// оставлено как валидная точка входа для будущих вариантов патча.
	void __fastcall H_ProcessInternal(void* self, void* frame, void* result);

''')

s = s[:i] + NEW + s[j:]
io.open(CPP, 'w', encoding='utf-8', newline='').write(s)
print('H_ProcessInternal очищена (счёт в стабе, вызов оригинала - хвостовой jmp)')

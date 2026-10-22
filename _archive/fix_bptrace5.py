# -*- coding: utf-8 -*-
# doit6 §4 (исправление 4): корректный вызов оригинала с сохранением security cookie.
#
# ДИАГНОЗ зависания: оригинал ProcessInternal вычисляет cookie как
#   XOR RAX(=[0x1448AFB30]), RSP
# где RSP - это RSP ПОСЛЕ пролога (PUSH x3; SUB RSP,0x80). Значит RSP при входе
# в оригинал обязан ТОЧНО совпадать с ожидаемым, иначе __security_check_cookie
# в эпилоге не сойдётся.
#
# Раньше обработчик делал call трамплина (RSP-8) => cookie не сходился => зависание.
#
# ПРАВИЛЬНАЯ СХЕМА:
#   обработчик (вход через jmp, RSP не тронут):
#       sub  rsp, 0x20      ; shadow space для вызова счётчика (alignment сохраняется)
#       call BpNote
#       add  rsp, 0x20      ; RSP снова как был
#       mov  r11, trampoline
#       jmp  r11            ; прыжок БЕЗ изменения RSP
#   трамплин:
#       PUSH RBX; PUSH RSI; PUSH RDI; SUB RSP,0x80   ; ровно пролог оригинала
#       jmp target+11
#   => оригинал видит ИДЕНТИЧНЫЙ RSP, cookie сходится, epilogue делает ret
#      к адресу возврата, который положил ВЫЗЫВАЮЩИЙ ProcessInternal.
import io, sys

CPP = r'C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp'
src = io.open(CPP, 'r', encoding='utf-8', newline='').read()
NL = '\r\n' if '\r\n' in src else '\n'


def blk(t):
    return t.replace('\n', NL)


OLD = blk('''		// Вызов оригинала: mov r11, трамплин; call r11; ret.
		// Код генерируется в RW-память (x64 MSVC не поддерживает inline asm).
		// Регистры self/frame/result уже в RCX/RDX/R8 (не трогаем).
		if (g_bp_call_code)
		{
			typedef void(__fastcall* Fn)(void*, void*, void*);
			reinterpret_cast<Fn>(g_bp_call_code)(self, frame, result);
		}
	}''')

NEW = blk('''		// Вызов оригинала БЕЗ изменения RSP: иначе security cookie оригинала
		// (XOR RAX,[0x1448AFB30], RSP) не сойдётся и функция зависнет.
		// Схема: sub rsp,0x20 (shadow) -> call счётчика -> add rsp,0x20 -> jmp трамплин.
		// Трамплин выполняет пролог оригинала (PUSH x3; SUB RSP,0x80) и прыгает
		// на target+11, поэтому оригинал видит ИДЕНТИЧНЫЙ RSP.
		__asm
		{
			sub  rsp, 20h
		}
		{
			std::string nm;
			if (BpFunctionName(frame, nm))
				BpNote(nm);
		}
		__asm
		{
			add  rsp, 20h
			mov  r11, g_bp_trampoline
			jmp  r11
		}
	}''')

if OLD in src:
    src = src.replace(OLD, NEW, 1)
    print('обработчик переведён на схему без изменения RSP')
else:
    print('ВНИМАНИЕ: текущий вид обработчика другой, разбираюсь')
    i = src.find('void H_ProcessInternal')
    print(repr(src[i:i + 900]))

# глобальная переменная с трамплином
if 'g_bp_trampoline' not in src.split('H_ProcessInternal')[0]:
    src = src.replace(blk('	void* g_bp_call_code = nullptr;          // сгенерированный "mov r11,tramp; call r11; ret"'),
                      blk('	void* g_bp_call_code = nullptr;          // сгенерированный код вызова\n'
                          '	void* g_bp_trampoline = nullptr;        // трамплин оригинала (глобальный)'), 1)

# в BpInstall: g_bp_trampoline = tramp; больше не нужен call_code
src = src.replace(blk('''		_o_ProcessInternal = tramp;
		g_bp_call_code = call_code;'''),
                  blk('''		_o_ProcessInternal = tramp;
		g_bp_trampoline = tramp;'''), 1)

io.open(CPP, 'w', encoding='utf-8', newline='').write(src)
print('bptrace: исправление cookie применено')

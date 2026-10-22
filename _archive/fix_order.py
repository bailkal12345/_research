# -*- coding: utf-8 -*-
# Перенос блоков: пауза (П5) - перед WriteResults (раньше всех использований),
# BpInit - после ядра bptrace (нужны BP_MAX_SLOTS и g_bp_qpc_freq).
import io

CPP = r'C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp'
src = io.open(CPP, 'r', encoding='utf-8', newline='').read()
NL = '\r\n' if '\r\n' in src else '\n'


def blk(t):
    return t.replace('\n', NL)


def cut(s, start_marker, end_marker):
    i = s.index(start_marker)
    j = s.index(end_marker, i)
    block = s[i:j]
    return s[:i] + s[j:], block


# --- вырезаем оба блока
src, both = cut(src, '	// ------------------------------------------------- пауза после сэмплер-окна (П5)',
                '	// ------------------------------------------------- bptrace (ARCH.md 3.5)')
_i = both.index('	// Инициализация структур bptrace')
cooldown = both[:_i]
init = both[_i:]

# --- пауза: перед WriteResults
anchor = '	void WriteResults()'
i = src.index(anchor)
src = src[:i] + cooldown + src[i:]

# --- BpInit: перед census-комментарием (после ядра и команд bptrace)
anchor2 = '	// ------------------------------------------------- census overlap-событий'
i = src.index(anchor2)
src = src[:i] + init + src[i:]

io.open(CPP, 'w', encoding='utf-8', newline='').write(src)
print('блоки переставлены: пауза -> перед WriteResults, BpInit -> после ядра bptrace')

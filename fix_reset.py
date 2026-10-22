# -*- coding: utf-8 -*-
import io

CPP = r'C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp'
src = io.open(CPP, encoding='utf-8', newline='').read()
NL = '\r\n' if '\r\n' in src else '\n'
anchor = '\t// Топ вызывающих'
RESET = ('\t// Сброс счётчиков на новое окно (подмена остаётся).\n'
         '\tvoid CmdBpTraceReset(RCONClientConnection*, RCONPacket*, UWorld*)\n'
         '\t{\n'
         '\t\tBpResetCounters();\n'
         '\t\tLogLine("bptrace: счётчики обнулены (окно переоткрыто)");\n'
         '\t}\n').replace('\n', NL)
if 'CmdBpTraceReset(' not in src.split('cmds.AddRconCommand')[0]:
    i = src.index(anchor)
    src = src[:i] + RESET + src[i:]
    io.open(CPP, 'w', encoding='utf-8', newline='').write(src)
    print('CmdBpTraceReset возвращён')
else:
    print('CmdBpTraceReset уже определён')

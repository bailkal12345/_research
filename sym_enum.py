# -*- coding: utf-8 -*-
# Перечень символов dbghelp вокруг заданного офсета TickProf.dll.
import sys
from ctypes import wintypes
import ctypes

DLL = r'C:\Dev\ARK-Server-Plugins\TickProf\TickProf\build\Release\TickProf.dll'
MAX_SYM_NAME = 2000

dbghelp = ctypes.WinDLL('dbghelp')
kernel32 = ctypes.WinDLL('kernel32')


class SYMBOL_INFO(ctypes.Structure):
    _fields_ = [
        ("SizeOfStruct", wintypes.ULONG), ("TypeIndex", wintypes.ULONG),
        ("Reserved", ctypes.c_uint64 * 2), ("Index", wintypes.ULONG),
        ("Size", wintypes.ULONG), ("ModBase", ctypes.c_uint64),
        ("Flags", wintypes.ULONG), ("Value", ctypes.c_uint64),
        ("Address", ctypes.c_uint64), ("Register", wintypes.ULONG),
        ("Scope", wintypes.ULONG), ("Tag", wintypes.ULONG),
        ("NameLen", wintypes.ULONG), ("MaxNameLen", wintypes.ULONG),
        ("Name", ctypes.c_char * MAX_SYM_NAME),
    ]


hproc = kernel32.GetCurrentProcess()
dbghelp.SymSetOptions(0x12)  # UNDNAME | LOAD_LINES
assert dbghelp.SymInitializeW(hproc, None, False)
BASE, SIZE = 0x180000000, 0x100000
dbghelp.SymLoadModuleExW(hproc, None, ctypes.c_wchar_p(DLL), None,
                         ctypes.c_uint64(BASE), ctypes.c_uint64(SIZE), None, 0)

offset = int(sys.argv[1], 16)

rows = []
ENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(SYMBOL_INFO), ctypes.c_ulong, ctypes.c_void_p)


def cb(sym, size_, ctx):
    s = sym.contents
    if s.NameLen > 0:
        rows.append((s.Address - BASE, s.Size, s.Name.decode('utf-8', 'replace')))
    return True


dbghelp.SymEnumSymbolsW(hproc, ctypes.c_uint64(BASE), None, ENUMPROC(cb), None)
rows.sort()

print('======== символы вокруг 0x%06X ========' % offset)
for off, size, name in rows:
    fits = off <= offset <= off + max(size, 0x10)
    if fits or abs(off - offset) < 0x300:
        tag = ' << ОКРЕСТНОСТЬ КРЭША' if fits else ''
        print('%06X  size=%-6s %s%s' % (off, size, name, tag))

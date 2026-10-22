# -*- coding: utf-8 -*-
# Символизация офсета внутри TickProf.dll по PDB через dbghelp (SymLoadModuleEx).
import ctypes, sys
from ctypes import wintypes

PDB = r'C:\Dev\ARK-Server-Plugins\TickProf\TickProf\build\Release\TickProf.pdb'
DLL = r'C:\Dev\ARK-Server-Plugins\TickProf\TickProf\build\Release\TickProf.dll'

dbghelp = ctypes.WinDLL('dbghelp')
kernel32 = ctypes.WinDLL('kernel32')

MAX_SYM_NAME = 2000

class SYMBOL_INFO(ctypes.Structure):
    _fields_ = [
        ("SizeOfStruct", wintypes.ULONG),
        ("TypeIndex", wintypes.ULONG),
        ("Reserved", ctypes.c_uint64 * 2),
        ("Index", wintypes.ULONG),
        ("Size", wintypes.ULONG),
        ("ModBase", ctypes.c_uint64),
        ("Flags", wintypes.ULONG),
        ("Value", ctypes.c_uint64),
        ("Address", ctypes.c_uint64),
        ("Register", wintypes.ULONG),
        ("Scope", wintypes.ULONG),
        ("Tag", wintypes.ULONG),
        ("NameLen", wintypes.ULONG),
        ("MaxNameLen", wintypes.ULONG),
        ("Name", ctypes.c_char * MAX_SYM_NAME),
    ]

hproc = kernel32.GetCurrentProcess()
SYMOPT_UNDNAME = 0x00000002
SYMOPT_LOAD_LINES = 0x00000010
assert dbghelp.SymSetOptions(SYMOPT_UNDNAME | SYMOPT_LOAD_LINES)
assert dbghelp.SymInitializeW(hproc, None, False), ctypes.get_last_error()

BASE = 0x180000000
SIZE = 0x100000
dll = ctypes.c_wchar_p(DLL)
dbghelp.SymLoadModuleExW(hproc, None, dll, None, ctypes.c_uint64(BASE), ctypes.c_uint64(SIZE), None, 0)
ctypes.set_last_error(0)

targets = [(a, name) for a, name in [
    (int(sys.argv[1], 16) if len(sys.argv) > 1 else None, 'заданный'),
]]
for addr_off, _ in targets:
    addr = BASE + addr_off
    si = SYMBOL_INFO()
    si.SizeOfStruct = ctypes.sizeof(SYMBOL_INFO) - MAX_SYM_NAME
    si.MaxNameLen = MAX_SYM_NAME
    disp = ctypes.c_uint64(0)
    ok = dbghelp.SymFromAddrW(hproc, ctypes.c_uint64(addr), ctypes.byref(disp), ctypes.byref(si))
    if ok:
        print('0x%06X -> %s + %d' % (addr_off, si.Name.decode(), disp.value))
    else:
        print('0x%06X -> символ не найден (err=%d)' % (addr_off, ctypes.get_last_error()))
    # строка
    class DISPLINE(ctypes.Structure):
        _fields_ = [("lineNumber", wintypes.DWORD), ("fileName", ctypes.c_char * 1024)]
    dl = DISPLINE()
    # SymGetLineFromAddrW64
    try:
        dbghelp.SymGetLineFromAddrW64.restype = ctypes.c_bool
        ok = dbghelp.SymGetLineFromAddrW64(hproc, ctypes.c_uint64(addr), ctypes.byref(disp), ctypes.byref(dl))
        if ok:
            print('   строка: %s:%d' % (dl.fileName.decode(), dl.lineNumber))
    except Exception as e:
        print('   (строки недоступны: %r)' % e)

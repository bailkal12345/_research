# -*- coding: utf-8 -*-
# Строка исходника для офсета TickProf.dll (SymGetLineFromAddrW64).
import sys
from ctypes import wintypes
import ctypes

DLL = r'C:\Dev\ARK-Server-Plugins\TickProf\TickProf\build\Release\TickProf.dll'

dbghelp = ctypes.WinDLL('dbghelp')
kernel32 = ctypes.WinDLL('kernel32')

hproc = kernel32.GetCurrentProcess()
dbghelp.SymSetOptions(0x10)  # LOAD_LINES
assert dbghelp.SymInitializeW(hproc, None, False)
BASE, SIZE = 0x180000000, 0x100000
dbghelp.SymLoadModuleExW(hproc, None, ctypes.c_wchar_p(DLL), None,
                         ctypes.c_uint64(BASE), ctypes.c_uint64(SIZE), None, 0)


class IMAGEHLP_LINEW64(ctypes.Structure):
    _fields_ = [
        ("SizeOfStruct", wintypes.ULONG),
        ("Key", wintypes.ULONG),
        ("LineNumber", wintypes.DWORD),
        ("FileName", ctypes.c_wchar_p),
        ("Address", ctypes.c_uint64),
    ]


offset = int(sys.argv[1], 16)
addr = ctypes.c_uint64(BASE + offset)
disp = wintypes.DWORD(0)
line = IMAGEHLP_LINEW64()
line.SizeOfStruct = ctypes.sizeof(line)
dbghelp.SymGetLineFromAddrW64.restype = ctypes.c_bool
ok = dbghelp.SymGetLineFromAddrW64(hproc, addr, ctypes.byref(disp), ctypes.byref(line))
if ok:
    print('0x%06X -> %s:%d (смещение в строке %d)' %
          (offset, line.FileName, line.LineNumber, disp.value))
    print('sym: %s' % line.FileName if line.Address == addr.value else '')
else:
    print('ошибка SymGetLine: %d' % kernel32.GetLastError())

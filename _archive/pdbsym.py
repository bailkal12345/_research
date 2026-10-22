# -*- coding: utf-8 -*-
# Резолвер имён функций ShooterGameServer.exe через PDB (dbghelp, ctypes).
# Проверено: модуль загружается по базе 0x40000000, символы PDB читаются.
import ctypes, ctypes.wintypes as wt, sys

EXE = r'C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ShooterGameServer.exe'

class SYMBOL_INFO(ctypes.Structure):
    _fields_ = [('SizeOfStruct', wt.ULONG), ('TypeIndex', wt.ULONG),
                ('Reserved', ctypes.c_ulonglong * 2), ('Index', wt.ULONG),
                ('Size', wt.ULONG), ('ModBase', ctypes.c_ulonglong),
                ('Flags', wt.ULONG), ('Value', ctypes.c_ulonglong),
                ('Address', ctypes.c_ulonglong), ('RegisterIndex', wt.ULONG),
                ('Register', wt.USHORT), ('Scope', wt.ULONG), ('Tag', wt.ULONG),
                ('NameLen', wt.ULONG), ('MaxNameLen', wt.ULONG)]

class IMAGEHLP_LINEW64(ctypes.Structure):
    _fields_ = [('SizeOfStruct', wt.DWORD), ('Key', ctypes.c_void_p),
                ('LineNumber', wt.DWORD), ('FileName', wt.LPWSTR),
                ('Address', ctypes.c_ulonglong)]

dbghelp = ctypes.WinDLL('dbghelp.dll', use_last_error=True)
hproc = ctypes.windll.kernel32.GetCurrentProcess()
BASE = None
SIZE = 8192

def init():
    global BASE
    if BASE is None:
        dbghelp.SymSetOptions(ctypes.c_uint(0x10 | 0x40))
        if not dbghelp.SymInitializeW(hproc, None, False):
            raise OSError('SymInitializeW err %d' % ctypes.get_last_error())
        BASE = dbghelp.SymLoadModuleExW(hproc, None, EXE, None, 0x40000000, 0x8000000, None, 0)
        if not BASE:
            raise OSError('SymLoadModuleExW err %d' % ctypes.get_last_error())
    return BASE

_cache = {}
def resolve(rva):
    """Возвращает (имя, смещение_от_начала_символа, размер_символа) или (None, None, None)."""
    if rva in _cache:
        return _cache[rva]
    base = init()
    buf = ctypes.create_string_buffer(SIZE)
    si = ctypes.cast(buf, ctypes.POINTER(SYMBOL_INFO))
    si.contents.SizeOfStruct = ctypes.sizeof(SYMBOL_INFO)
    si.contents.MaxNameLen = (SIZE - ctypes.sizeof(SYMBOL_INFO)) // 2 - 1
    disp = ctypes.c_ulonglong(0)
    ok = dbghelp.SymFromAddr(hproc, ctypes.c_ulonglong(base + rva), ctypes.byref(disp), si)
    if not ok:
        res = (None, None, None)
    else:
        # ANSI-вариант: имя в байтах сразу после структуры (по терминатору)
        raw = ctypes.string_at(ctypes.byref(si.contents, ctypes.sizeof(SYMBOL_INFO)),
                               min(2048, SIZE - ctypes.sizeof(SYMBOL_INFO)))
        nm = raw.split(b'\0')[0].decode('mbcs', 'replace')
        res = (nm if nm else None, disp.value, si.contents.Size)
    _cache[rva] = res
    return res

def resolve_lines(rva):
    base = init()
    li = IMAGEHLP_LINEW64()
    li.SizeOfStruct = ctypes.sizeof(IMAGEHLP_LINEW64)
    ldisp = ctypes.c_ulonglong(0)
    if dbghelp.SymGetLineFromAddrW64(hproc, ctypes.c_ulonglong(base + rva),
                                     ctypes.byref(ldisp), ctypes.byref(li)):
        return (li.FileName or None), li.LineNumber
    return None, None

if __name__ == '__main__':
    for a in sys.argv[1:]:
        rva = int(a, 16)
        nm, disp, sz = resolve(rva)
        fn, ln = resolve_lines(rva)
        if nm:
            print('RVA 0x%X: %s (+%d, size %d)' % (rva, nm, disp, sz))
            if fn:
                print('            %s : %d' % (fn, ln))
        else:
            fnstr = (' %s' % fn) if fn else ''
            print('RVA 0x%X: <нет символа>%s' % (rva, fnstr))

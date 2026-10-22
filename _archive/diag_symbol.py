import ctypes, ctypes.wintypes as wt
import pdbsym as p

class SYMBOL_INFO(ctypes.Structure):
    _fields_ = [('SizeOfStruct', wt.ULONG), ('TypeIndex', wt.ULONG),
                ('Reserved', ctypes.c_ulonglong * 2), ('Index', wt.ULONG),
                ('Size', wt.ULONG), ('ModBase', ctypes.c_ulonglong),
                ('Flags', wt.ULONG), ('Value', ctypes.c_ulonglong),
                ('Address', ctypes.c_ulonglong), ('RegisterIndex', wt.ULONG),
                ('Register', wt.USHORT), ('Scope', wt.ULONG), ('Tag', wt.ULONG),
                ('NameLen', wt.ULONG), ('MaxNameLen', wt.ULONG)]

base = p.init()
size = 8192
buf = ctypes.create_string_buffer(size)
si = ctypes.cast(buf, ctypes.POINTER(SYMBOL_INFO))
si.contents.SizeOfStruct = ctypes.sizeof(SYMBOL_INFO)
si.contents.MaxNameLen = (size - ctypes.sizeof(SYMBOL_INFO)) // 2 - 1
nm = ctypes.c_wchar_p('UGameEngine::GetMaxTickRate')
ok = p.dbghelp.SymFromNameW(p.hproc, nm, si)
print('SymFromNameW ok=', ok, 'err=', ctypes.get_last_error())
if ok:
    print('NameLen=', si.contents.NameLen, 'Size=', si.contents.Size, 'Addr-Base=', hex(si.contents.Address - base))
    raw = ctypes.string_at(ctypes.byref(si.contents, 88), 200)
    print('utf16@88:', raw.decode('utf-16-le', 'replace').split('\0')[0])
# и от адреса: 0x276A0B0 сырьём
si.contents.SizeOfStruct = ctypes.sizeof(SYMBOL_INFO)
si.contents.MaxNameLen = (size - ctypes.sizeof(SYMBOL_INFO)) // 2 - 1
disp = ctypes.c_ulonglong(0)
ok2 = p.dbghelp.SymFromAddrW(p.hproc, ctypes.c_ulonglong(base + 0x276A0B0), ctypes.byref(disp), si)
print('SymFromAddrW ok=', ok2)
if ok2:
    print('NameLen=', si.contents.NameLen, 'MaxNameLen=', si.contents.MaxNameLen, 'Size=', si.contents.Size)
    raw = ctypes.string_at(ctypes.byref(si.contents, 88), 300)
    print('utf16@88:', raw.decode('utf-16-le', 'replace').split('\0')[0])

# -*- coding: utf-8 -*-
# Полный индекс функций exe из PDB через SymEnumSymbolsW + кэш на диск.
# Затем резолвер адрес->имя по индексу (с точной границей функций Address..Address+Size).
import ctypes, ctypes.wintypes as wt, bisect, json, os, sys

import pdbsym as p

class SYMBOL_INFO(ctypes.Structure):
    _fields_ = [('SizeOfStruct', wt.ULONG), ('TypeIndex', wt.ULONG),
                ('Reserved', ctypes.c_ulonglong * 2), ('Index', wt.ULONG),
                ('Size', wt.ULONG), ('ModBase', ctypes.c_ulonglong),
                ('Flags', wt.ULONG), ('Value', ctypes.c_ulonglong),
                ('Address', ctypes.c_ulonglong), ('RegisterIndex', wt.ULONG),
                ('Register', wt.USHORT), ('Scope', wt.ULONG), ('Tag', wt.ULONG),
                ('NameLen', wt.ULONG), ('MaxNameLen', wt.ULONG)]

CACHE = r'C:\Dev\_research\pdb_func_index.json'

def build_index(max_n=None):
    """arg: max_n — лимит символов (для отладки). Возвращает dict rva->имя и список (rva,size)."""
    base = p.init()
    CB = ctypes.WINFUNCTYPE(wt.BOOL, ctypes.POINTER(SYMBOL_INFO), wt.ULONG,
                            ctypes.c_ulonglong, ctypes.c_void_p)
    funcs = []  # (rva, size, name)

    def cb(si, sz, addr, ctx):
        c = si.contents
        if c.Tag == 5 and c.Size > 0:  # SYMTAG.Function
            n = c.NameLen
            if n <= 0:
                return True
            nb = min(n, 511)
            raw = ctypes.string_at(ctypes.byref(c, 88), nb)
            nm = raw.decode('utf-16-le', 'replace').split('\0')[0]
            funcs.append((c.Address - base, c.Size, nm))
        return True

    ok = p.dbghelp.SymEnumSymbolsW(p.hproc, ctypes.c_ulonglong(base), None, CB(cb), None)
    funcs.sort()
    return funcs

def main():
    if os.path.exists(CACHE):
        with open(CACHE, 'r', encoding='utf-8') as f:
            idx = json.load(f)
        print('кэш загружен: %d функций' % len(idx['funcs']))
    else:
        funcs = build_index()
        print('собрано: %d функций' % len(funcs))
        idx = {'funcs': [[a, b, c] for a, b, c in funcs]}
        with open(CACHE, 'w', encoding='utf-8') as f:
            json.dump(idx, f, ensure_ascii=False)
        print('кэш сохранён:', CACHE)
    starts = [x[0] for x in idx['funcs']]
    print('пример: 0x276A0B0 ->', end=' ')
    i = bisect.bisect_right(starts, 0x276A0B0) - 1
    print(idx['funcs'][i][2] if i >= 0 else '?')

def name_of(rva, idx=None):
    if idx is None:
        idx = INDEX
    i = bisect.bisect_right(idx._starts, rva) - 1
    if i < 0:
        return None
    r0, sz, nm = idx._funcs[i]
    if rva < r0 + sz:
        return (nm, rva - r0, sz)
    return None

class IDX:
    def __init__(self):
        with open(CACHE, 'r', encoding='utf-8') as f:
            self.funcs = [(a, b, c) for a, b, c in json.load(open(CACHE, encoding='utf-8'))['funcs']]
        self._starts = [x[0] for x in self.funcs]

INDEX = None

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'build':
        main()
    else:
        INDEX = IDX()
        print('index functions:', len(INDEX.funcs))

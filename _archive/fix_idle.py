import io
p = "exp_idle.py"
s = io.open(p, encoding="utf-8").read()
s = s.replace('    nt = ctypes.c_uint64(k32.GetModuleHandleW("ntdll.dll"))',
              '    k32.GetModuleHandleW.restype = ctypes.c_void_p\n'
              '    k32.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]\n'
              '    nt_ptr = k32.GetModuleHandleW(ctypes.c_wchar_p("ntdll.dll"))\n'
              '    nt = ctypes.c_uint64(nt_ptr if nt_ptr else 0)\n'
              '    if not nt.value:\n'
              '        print("ntdll не найдена")\n'
              '        return 3')
io.open(p, "w", encoding="utf-8").write(s)
print("ok")

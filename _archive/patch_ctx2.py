import io
p = "stackdump.py"
src = io.open(p, encoding="utf-8").read()

# вместо ручного CONTEXT читаем сырой буфер по документированным смещениям x64 CONTEXT
start = src.index("CONTEXT_CONTROL = ")
end = src.index("def find_pid(")
src = src[:start] + '''CONTEXT_CONTROL = 0x00100001  # CONTEXT_CONTROL|CONTEXT_INTEGER
CONTEXT_SIZE = 1232
OFF_RIP = 0x108
OFF_RSP = 0xA8
OFF_RBP = 0xB0


''' + src[end:]

src = src.replace('''    k32.SuspendThread(h)
    ctx = CONTEXT()
    ctx.ContextFlags = CONTEXT_CONTROL
    ok = k32.GetThreadContext(h, C.byref(ctx))
    rip, rsp = ctx.Rip, ctx.Rsp
    k32.ResumeThread(h)

    if not ok:
        print("GetThreadContext failed %d" % C.get_last_error())
        return
''', '''    buf_ctx = C.create_string_buffer(CONTEXT_SIZE)
    struct.pack_into("<I", buf_ctx, 0x30, CONTEXT_CONTROL)
    k32.SuspendThread(h)
    ok = k32.GetThreadContext(h, C.cast(buf_ctx, C.c_void_p))
    raw = buf_ctx.raw
    rip, rsp, rbp = (struct.unpack_from("<Q", raw, OFF_RIP)[0],
                     struct.unpack_from("<Q", raw, OFF_RSP)[0],
                     struct.unpack_from("<Q", raw, OFF_RBP)[0])
    k32.ResumeThread(h)

    if not ok:
        print("GetThreadContext failed %d" % C.get_last_error())
        return
''')

src = src.replace('''    k32.ReadProcessMemory.argtypes = [W.HANDLE, C.c_void_p, C.c_void_p, C.c_size_t, C.POINTER(C.c_size_t)]
    proc = C.WinDLL("kernel32", use_last_error=True).OpenProcess(0x0010 | 0x0400, False, pid)''',
'''    k32.ReadProcessMemory.argtypes = [W.HANDLE, C.c_void_p, C.c_void_p, C.c_size_t, C.POINTER(C.c_size_t)]
    k32.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
    k32.OpenProcess.restype = W.HANDLE
    proc = k32.OpenProcess(0x0010 | 0x0400, False, pid)''')

io.open(p, "w", encoding="utf-8").write(src)
print("patched")

import io
p = "exp_idle.py"
s = io.open(p, encoding="utf-8").read()
# выравнивание по 16 байт — обязательное требование для x64 CONTEXT
s = s.replace('''    ctx = C.create_string_buffer(CONTEXT_SIZE)
    t0 = time.time()''','''    # CONTEXT обязан быть выровнен по 16 байт, иначе GetThreadContext
    # возвращает TRUE, но не заполняет буфер (RIP читается как 0).
    raw_ctx = C.create_string_buffer(CONTEXT_SIZE + 16)
    ctx_addr = (C.addressof(raw_ctx) + 15) & ~15
    t0 = time.time()''')
s = s.replace('''        ctx = C.create_string_buffer(CONTEXT_SIZE)
        struct.pack_into("<I", ctx, 0, CONTEXT_ALL)
        if k32.SuspendThread(h) == 0xFFFFFFFF:
            break
        ok = k32.GetThreadContext(h, C.cast(ctx, C.c_void_p))''','''        struct.pack_into("<I", raw_ctx, 0, CONTEXT_ALL)
        if k32.SuspendThread(h) == 0xFFFFFFFF:
            break
        ok = k32.GetThreadContext(h, C.c_void_p(ctx_addr))''')
s = s.replace("        rip = struct.unpack_from(\"<Q\", ctx, OFF_RIP)[0]\n        rsp = struct.unpack_from(\"<Q\", ctx, OFF_RSP)[0]",
              "        rip = struct.unpack_from(\"<Q\", raw_ctx, OFF_RIP)[0]\n        rsp = struct.unpack_from(\"<Q\", raw_ctx, OFF_RSP)[0]")
# правильные смещения x64 CONTEXT
s = s.replace("OFF_RSP = 0x98\nOFF_RIP = 0xF8", "OFF_RSP = 0x98   # см. OFF_RSP_X64 ниже\nOFF_RIP = 0xF8")
s = s.replace("CONTEXT_ALL = 0x0001003F\nCONTEXT_SIZE = 1232",
              "CONTEXT_ALL = 0x0001003F\nCONTEXT_SIZE = 1232\n"
              "# x64 CONTEXT: ContextFlags @0x30, Rsp @0x298, Rip @0x2F8\n"
              "OFF_FLAGS_X64 = 0x30\nOFF_RSP_X64 = 0x298\nOFF_RIP_X64 = 0x2F8")
s = s.replace('        struct.pack_into("<I", raw_ctx, 0, CONTEXT_ALL)', '        struct.pack_into("<I", raw_ctx, OFF_FLAGS_X64, CONTEXT_ALL)')
s = s.replace('        rip = struct.unpack_from("<Q", raw_ctx, OFF_RIP)[0]\n        rsp = struct.unpack_from("<Q", raw_ctx, OFF_RSP)[0]',
              '        rip = struct.unpack_from("<Q", raw_ctx, OFF_RIP_X64)[0]\n        rsp = struct.unpack_from("<Q", raw_ctx, OFF_RSP_X64)[0]')
io.open(p, "w", encoding="utf-8").write(s)
print("ok")

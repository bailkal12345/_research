import sys, time, ctypes as C, struct
sys.path.insert(0, r"C:\Dev\_research")
import exp_idle as E, threadcpu
tid = E.game_tid(); pid = threadcpu.find_pid()[0]
h = E.k32.OpenThread(E.THREAD_SUSPEND_RESUME|E.THREAD_GET_CONTEXT|E.THREAD_QUERY_INFORMATION, False, tid)
mods = E.module_map(pid)
raw = C.create_string_buffer(1232+32)
addr = (C.addressof(raw)+15) & ~15
def modof(v):
    for s,e,n in mods:
        if s <= v < e: return "игра" if n=="#0" else n
    return "ядро/иное"
for it in range(5):
    raw[:] = b"\0"*len(raw)
    struct.pack_into("<I", raw, 0, 0x0001003F)
    E.k32.SuspendThread(h)
    ok = E.k32.GetThreadContext(h, C.c_void_p(addr))
    E.k32.ResumeThread(h)
    hits = []
    for off in range(0, 1232, 8):
        v = struct.unpack_from("<Q", raw, off)[0]
        if v > 0x7FF000000000:
            hits.append((off, v, modof(v)))
    print("ok=%s кандидаты: %s" % (ok, ", ".join("0x%X=%X(%s)" % (o,v,m) for o,v,m in hits[:6])))
    time.sleep(0.004)

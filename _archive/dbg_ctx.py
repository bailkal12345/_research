import sys, time, ctypes as C, struct
sys.path.insert(0, r"C:\Dev\_research")
import exp_idle as E, threadcpu
tid = E.game_tid(); pid = threadcpu.find_pid()[0]
h = E.k32.OpenThread(E.THREAD_SUSPEND_RESUME|E.THREAD_GET_CONTEXT|E.THREAD_QUERY_INFORMATION, False, tid)
mods = E.module_map(pid)
ctx = C.create_string_buffer(1232)
struct.pack_into("<I", ctx, 0x30, 0x0001003F)   # ContextFlags по правильному смещению
E.k32.SuspendThread(h)
ok = E.k32.GetThreadContext(h, C.cast(ctx, C.c_void_p))
E.k32.ResumeThread(h)
print("GetThreadContext ok=%s" % ok)
raw = ctx.raw
for off in range(0, 1232, 8):
    v = struct.unpack_from("<Q", raw, off)[0]
    if any(s <= v < e for s, e, n in mods):
        nm = next(n for s, e, n in mods if s <= v < e)
        print("   смещение 0x%03X: %016X  (модуль %s)" % (off, v, nm))

import sys, time, ctypes as C, struct
sys.path.insert(0, r"C:\Dev\_research")
import exp_idle as E, threadcpu
tid = E.game_tid(); pid = threadcpu.find_pid()[0]
h = E.k32.OpenThread(E.THREAD_SUSPEND_RESUME|E.THREAD_GET_CONTEXT|E.THREAD_QUERY_INFORMATION, False, tid)
mods = E.module_map(pid)
print("tid=%d pid=%d модулей=%d" % (tid, pid, len(mods)))
for s,e,n in mods[:10]:
    print("   %016X..%016X  %s" % (s,e,n))
rips=[]
for _ in range(10):
    ctx = C.create_string_buffer(E.CONTEXT_SIZE)
    struct.pack_into("<I", ctx, 0, E.CONTEXT_ALL)
    E.k32.SuspendThread(h)
    ok = E.k32.GetThreadContext(h, C.cast(ctx, C.c_void_p))
    E.k32.ResumeThread(h)
    rips.append((ok, struct.unpack_from("<Q", ctx, E.OFF_RIP)[0], struct.unpack_from("<Q", ctx, E.OFF_RSP)[0]))
for ok, rip, rsp in rips:
    inmod = next((n for s,e,n in mods if s <= rip < e), None)
    print("   ok=%d RIP=%016X RSP=%016X модуль=%s" % (ok, rip, rsp, inmod))

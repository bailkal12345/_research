import sys, time, ctypes as C, struct
sys.path.insert(0, r"C:\Dev\_research")
import exp_idle as E, threadcpu
tid = E.game_tid(); pid = threadcpu.find_pid()[0]
h = E.k32.OpenThread(E.THREAD_SUSPEND_RESUME|E.THREAD_GET_CONTEXT|E.THREAD_QUERY_INFORMATION, False, tid)
mods = module_map = E.module_map(pid)
names = ["Rax","Rcx","Rdx","Rbx","Rsp","Rbp","Rsi","Rdi","R8","R9","R10","R11","R12","R13","R14","R15","Rip"]
def modof(v):
    for s,e,n in mods:
        if s <= v < e: return n
    return "—" if v < 0x7FF000000000 else "ЯДРО"
for it in range(8):
    ctx = C.create_string_buffer(1232)
    struct.pack_into("<I", ctx, 0x30, 0x0001003F)
    E.k32.SuspendThread(h)
    ok = E.k32.GetThreadContext(h, C.cast(ctx, C.c_void_p))
    E.k32.ResumeThread(h)
    rip = struct.unpack_from("<Q", ctx, 0x2F8)[0]
    rsp = struct.unpack_from("<Q", ctx, 0x298)[0]
    print("ok=%s RIP=%016X (%s) RSP=%016X" % (ok, rip, modof(rip), rsp))
    time.sleep(0.004)

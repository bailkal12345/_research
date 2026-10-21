import sys, time, ctypes as C, struct
sys.path.insert(0, r"C:\Dev\_research")
import exp_idle as E, threadcpu
tid = E.game_tid(); pid = threadcpu.find_pid()[0]
h = E.k32.OpenThread(E.THREAD_SUSPEND_RESUME|E.THREAD_GET_CONTEXT|E.THREAD_QUERY_INFORMATION, False, tid)
mods = E.module_map(pid)
raw = C.create_string_buffer(1232+16)
addr = (C.addressof(raw)+15) & ~15
def modof(v):
    for s,e,n in mods:
        if s <= v < e: return n
    return "пользователь.код" if 0x7FF000000000 < v < 0x800000000000 else ("ЯДРО" if v > 0xF00000000000 else "низкий")
for i in range(10):
    struct.pack_into("<I", raw, 0x30, 0x0001003F)
    E.k32.SuspendThread(h)
    ok = E.k32.GetThreadContext(h, C.c_void_p(addr))
    E.k32.ResumeThread(h)
    rip = struct.unpack_from("<Q", raw, 0x2F8)[0]
    rsp = struct.unpack_from("<Q", raw, 0x298)[0]
    print("ok=%s RIP=%016X (%s) RSP=%016X" % (ok, rip, modof(rip), rsp))
    time.sleep(0.004)

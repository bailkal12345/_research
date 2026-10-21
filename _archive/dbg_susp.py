import sys, time, ctypes as C, struct
sys.path.insert(0, r"C:\Dev\_research")
import exp_idle as E, threadcpu
tid = E.game_tid(); pid = threadcpu.find_pid()[0]
h = E.k32.OpenThread(E.THREAD_SUSPEND_RESUME|E.THREAD_GET_CONTEXT|E.THREAD_QUERY_INFORMATION, False, tid)
print("handle=%s tid=%d" % (h, tid))
raw = C.create_string_buffer(1232+16)
addr = (C.addressof(raw)+15) & ~15
struct.pack_into("<I", raw, 0x30, 0x0001003F)
C.set_last_error(0)
r = E.k32.SuspendThread(h)
e1 = C.get_last_error()
ok = E.k32.GetThreadContext(h, C.c_void_p(addr))
e2 = C.get_last_error()
rsp = E.k32.ResumeThread(h)
rip = struct.unpack_from("<Q", raw, 0x2F8)[0]
print("SuspendThread=%s err=%d | GetThreadContext ok=%s err=%d | Resume=%s | RIP=%016X" % (r, e1, ok, e2, rsp, rip))

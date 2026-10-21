# -*- coding: utf-8 -*-
"""
Быстрый «где завис поток»: снимает RIP GameThread и разбирает стек на живом процессе.

    python stackdump.py [--pid 12345] [--tid 4940] [--frames 20]

RIP/RSP читаются через SuspendThread + GetThreadContext (сырой буфер x64 CONTEXT,
смещения из winnt.h), стек разбирается эвристически: берём окно над RSP и оставляем
только значения, попадающие в образ игры. Символизация — по таблице pdbsym.exe.
"""
import argparse
import bisect
import ctypes as C
import ctypes.wintypes as W
import os
import sqlite3
import struct

k32 = C.WinDLL("kernel32", use_last_error=True)
k32.OpenThread.argtypes = [W.DWORD, W.BOOL, W.DWORD]
k32.OpenThread.restype = W.HANDLE
k32.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
k32.OpenProcess.restype = W.HANDLE
k32.GetThreadContext.argtypes = [W.HANDLE, C.c_void_p]
k32.GetThreadContext.restype = W.BOOL
k32.ReadProcessMemory.argtypes = [W.HANDLE, C.c_void_p, C.c_void_p, C.c_size_t, C.POINTER(C.c_size_t)]
k32.SuspendThread.argtypes = [W.HANDLE]
k32.ResumeThread.argtypes = [W.HANDLE]
k32.CreateToolhelp32Snapshot.restype = W.HANDLE

CONTEXT_ALL = 0x0001003F
CONTEXT_SIZE = 1232
# Смещения x64 CONTEXT: Segment Registers здесь WORD, из-за чего Rip лежит по 0xF8,
# а не 0x108 (проверено эмпирически на живом процессе).
OFF_RSP = 0x98
OFF_RBP = 0xA0
OFF_RIP = 0xF8
OFF_FLAGS = 0x30

THREAD_SUSPEND_RESUME = 0x0002
THREAD_GET_CONTEXT = 0x0008
THREAD_QUERY_INFORMATION = 0x0040
PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400


def find_pid(name="ShooterGameServer.exe"):
    class PE32(C.Structure):
        _fields_ = [
            ("dwSize", W.DWORD), ("cntUsage", W.DWORD), ("th32ProcessID", W.DWORD),
            ("th32DefaultHeapID", C.c_size_t), ("th32ModuleID", W.DWORD), ("cntThreads", W.DWORD),
            ("th32ParentProcessID", W.DWORD), ("pcPriClassBase", W.LONG), ("dwFlags", W.DWORD),
            ("szExeFile", W.WCHAR * 260),
        ]

    k32.Process32FirstW.argtypes = [W.HANDLE, C.POINTER(PE32)]
    k32.Process32NextW.argtypes = [W.HANDLE, C.POINTER(PE32)]
    snap = k32.CreateToolhelp32Snapshot(0x00000002, 0)
    pe = PE32()
    pe.dwSize = C.sizeof(pe)
    out = []
    if k32.Process32FirstW(snap, C.byref(pe)):
        while True:
            if pe.szExeFile.lower() == name.lower():
                out.append(pe.th32ProcessID)
            if not k32.Process32NextW(snap, C.byref(pe)):
                break
    k32.CloseHandle(snap)
    return out[0] if out else 0


def threads_of(pid):
    class TE32(C.Structure):
        _fields_ = [
            ("dwSize", W.DWORD), ("cntUsage", W.DWORD), ("th32ThreadID", W.DWORD),
            ("th32OwnerProcessID", W.DWORD), ("tpBasePri", W.LONG), ("tpDeltaPri", W.LONG),
            ("dwFlags", W.DWORD),
        ]

    k32.Thread32First.argtypes = [W.HANDLE, C.POINTER(TE32)]
    k32.Thread32Next.argtypes = [W.HANDLE, C.POINTER(TE32)]
    snap = k32.CreateToolhelp32Snapshot(0x00000004, 0)
    te = TE32()
    te.dwSize = C.sizeof(te)
    out = []
    if k32.Thread32First(snap, C.byref(te)):
        while True:
            if te.th32OwnerProcessID == pid:
                out.append(te.th32ThreadID)
            if not k32.Thread32Next(snap, C.byref(te)):
                break
    k32.CloseHandle(snap)
    return out


def module_base(pid):
    class ME32(C.Structure):
        _fields_ = [
            ("dwSize", W.DWORD), ("th32ModuleID", W.DWORD), ("th32ProcessID", W.DWORD),
            ("GlblcntUsage", W.DWORD), ("ProccntUsage", W.DWORD),
            ("modBaseAddr", C.POINTER(C.c_ubyte)), ("modBaseSize", W.DWORD),
            ("hModule", W.HMODULE), ("szModule", W.WCHAR * 256), ("szExePath", W.WCHAR * 260),
        ]

    k32.Module32FirstW.argtypes = [W.HANDLE, C.POINTER(ME32)]
    k32.Module32NextW.argtypes = [W.HANDLE, C.POINTER(ME32)]
    snap = k32.CreateToolhelp32Snapshot(0x00000008 | 0x00000010, pid)
    me = ME32()
    me.dwSize = C.sizeof(me)
    base = size = 0
    if k32.Module32FirstW(snap, C.byref(me)):
        while True:
            if me.szModule.lower() == "shootergameserver.exe":
                base = C.cast(me.modBaseAddr, C.c_void_p).value
                size = me.modBaseSize
                break
            if not k32.Module32NextW(snap, C.byref(me)):
                break
    k32.CloseHandle(snap)
    return base, size


class Syms:
    def __init__(self, db):
        con = sqlite3.connect(db)
        rows = con.execute("SELECT rva, name, size FROM fn WHERE tag=5 ORDER BY rva").fetchall()
        con.close()
        best = {}
        for rva, name, size in rows:
            if rva not in best or len(name) > len(best[rva][0]):
                best[rva] = (name, size)
        items = sorted(best.items())
        self.rvas = [r for r, _ in items]
        self.info = [(n, s if s > 0 else 0x40) for _, (n, s) in items]

    def find(self, rva):
        i = bisect.bisect_right(self.rvas, rva) - 1
        if i < 0:
            return None
        r0 = self.rvas[i]
        n, s = self.info[i]
        return n if rva < r0 + s else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, default=0)
    ap.add_argument("--tid", type=int, default=0)
    ap.add_argument("--frames", type=int, default=20)
    here = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument("--db", default=os.path.join(here, "v361.sqlite"))
    args = ap.parse_args()

    pid = args.pid or find_pid()
    if not pid:
        print("process not found")
        return
    base, size = module_base(pid)
    print("pid=%d image=0x%X..0x%X size=0x%X" % (pid, base, base + size, size))

    tid = args.tid
    if not tid:
        print("give --tid (see threadcpu.py output)")
        return

    h = k32.OpenThread(THREAD_SUSPEND_RESUME | THREAD_GET_CONTEXT | THREAD_QUERY_INFORMATION, False, tid)
    if not h:
        print("OpenThread failed %d" % C.get_last_error())
        return

    ctx = C.create_string_buffer(CONTEXT_SIZE)
    struct.pack_into("<I", ctx, OFF_FLAGS, CONTEXT_ALL)

    k32.SuspendThread(h)
    ok = k32.GetThreadContext(h, C.cast(ctx, C.c_void_p))
    err = C.get_last_error()
    k32.ResumeThread(h)

    raw = ctx.raw
    rip = struct.unpack_from("<Q", raw, OFF_RIP)[0]
    rsp = struct.unpack_from("<Q", raw, OFF_RSP)[0]
    rbp = struct.unpack_from("<Q", raw, OFF_RBP)[0]

    print("GetThreadContext ok=%s err=%d" % (ok, err))
    print("RIP=0x%X RSP=0x%X RBP=0x%X" % (rip, rsp, rbp))
    if not rip:
        return

    syms = Syms(args.db)
    print("  at: %s" % (syms.find(rip - base) or "<not in image>"))

    proc = k32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
    if not proc:
        print("OpenProcess failed %d" % C.get_last_error())
        return

    span = 16 * 1024
    buf = C.create_string_buffer(span)
    read = C.c_size_t(0)
    C.set_last_error(0)
    got = k32.ReadProcessMemory(proc, C.c_void_p(rsp), buf, span, C.byref(read))
    if read.value == 0:
        print("ReadProcessMemory failed %d" % C.get_last_error())
        return

    print("\nreturn addresses found on the stack:")
    seen = 0
    data = buf.raw[: read.value]
    prev = None
    for off in range(0, len(data) - 8, 8):
        (val,) = struct.unpack_from("<Q", data, off)
        if not (base <= val < base + size):
            continue
        n = syms.find(val - base)
        if not n or n == prev:
            continue
        prev = n
        print("  rsp+0x%05X  %s" % (off, n))
        seen += 1
        if seen >= args.frames:
            break
    k32.CloseHandle(proc)
    k32.CloseHandle(h)


if __name__ == "__main__":
    main()
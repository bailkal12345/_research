# -*- coding: utf-8 -*-
"""
П7: кто укладывает GameThread в NtDelayExecution / NtWaitForSingleObject.

Загадка из брифа: при лимите 120 и кадре 8.96 мс штатный pacing-сон
(1/120 = 8.33 мс) стрелять не должен, а NtDelayExecution занимает 24.4%
сэмплов, NtWaitForSingleObject — ещё 4.1%. Значит спит кто-то другой.

Техника capture повторяет рабочий stackdump.py: буфер CONTEXT фиксированного
размера и чтение полей по фиксированным смещениям (Rip=0xF8, Rsp=0x98).
Рукописная структура ctypes в предыдущей версии давала неверный RIP —
это и было причиной нулевых попаданий.

Дополнительно: полный набор модулей процесса, чтобы отличить «пользовательский
код» от ядра и классифицировать ожидание.

    python exp_idle.py [--samples 300] [--interval 0.002]
"""
import argparse
import bisect
import ctypes as C
import sqlite3
import struct
import sys
import time
from ctypes import wintypes as W

k32 = C.WinDLL("kernel32", use_last_error=True)
psapi = C.WinDLL("psapi", use_last_error=True)

k32.OpenThread.restype = W.HANDLE
k32.OpenProcess.restype = W.HANDLE
k32.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
k32.GetThreadContext.argtypes = [W.HANDLE, C.c_void_p]
k32.GetThreadContext.restype = W.BOOL
k32.ReadProcessMemory.argtypes = [W.HANDLE, C.c_void_p, C.c_void_p, C.c_size_t, C.POINTER(C.c_size_t)]
k32.SuspendThread.argtypes = [W.HANDLE]
k32.ResumeThread.argtypes = [W.HANDLE]

CONTEXT_ALL = 0x0001003F
CONTEXT_SIZE = 1232
# x64 CONTEXT: ContextFlags @0x30, Rsp @0x298, Rip @0x2F8
OFF_FLAGS_X64 = 0x30
OFF_RSP_X64 = 0x298
OFF_RIP_X64 = 0x2F8
OFF_RSP = 0x98   # см. OFF_RSP_X64 ниже
OFF_RIP = 0xF8
STACK_DEPTH = 64

THREAD_SUSPEND_RESUME = 0x0002
THREAD_GET_CONTEXT = 0x0008
THREAD_QUERY_INFORMATION = 0x0040
PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400

LOG = r"C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi\Plugins\TickProf\TickProf.log"


def game_tid():
    try:
        with open(LOG, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        return 0
    for ln in reversed(lines):
        if "game thread tid=" in ln:
            return int(ln.strip().split("tid=")[-1])
    return 0


def find_pid(name="ShooterGameServer.exe"):
    class PE32(C.Structure):
        _fields_ = [("dwSize", W.DWORD), ("cntUsage", W.DWORD), ("th32ProcessID", W.DWORD),
                    ("th32DefaultHeapID", C.c_size_t), ("th32ModuleID", W.DWORD),
                    ("cntThreads", W.DWORD), ("th32ParentProcessID", W.DWORD),
                    ("pcPriClassBase", W.LONG), ("dwFlags", W.DWORD), ("szExeFile", W.WCHAR * 260)]

    k32.Process32FirstW.argtypes = [W.HANDLE, C.POINTER(PE32)]
    k32.Process32NextW.argtypes = [W.HANDLE, C.POINTER(PE32)]
    snap = k32.CreateToolhelp32Snapshot(0x00000002, 0)
    pe = PE32()
    pe.dwSize = C.sizeof(pe)
    if not k32.Process32FirstW(snap, C.byref(pe)):
        return 0
    while True:
        if pe.szExeFile == name:
            k32.CloseHandle(snap)
            return pe.th32ProcessID
        pe.dwSize = C.sizeof(pe)
        if not k32.Process32NextW(snap, C.byref(pe)):
            break
    k32.CloseHandle(snap)
    return 0


def module_map(pid):
    """[(start, end, name)] для всех модулей процесса."""
    class MODULEINFO(C.Structure):
        _fields_ = [("lpBaseOfDll", C.c_void_p), ("SizeOfImage", W.DWORD), ("EntryPoint", C.c_void_p)]

    psapi.EnumProcessModules.restype = W.BOOL
    psapi.EnumProcessModules.argtypes = [W.HANDLE, C.POINTER(C.c_void_p), W.DWORD,
                                         C.POINTER(W.DWORD)]
    psapi.GetModuleInformation.restype = W.BOOL
    psapi.GetModuleInformation.argtypes = [W.HANDLE, C.c_void_p, C.POINTER(MODULEINFO), W.DWORD]

    ph = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not ph:
        return []
    mods = (C.c_void_p * 1024)()
    needed = W.DWORD()
    if not psapi.EnumProcessModules(ph, mods, C.sizeof(mods), C.byref(needed)):
        k32.CloseHandle(ph)
        return []
    out = []
    for i in range(needed.value // C.sizeof(C.c_void_p)):
        mi = MODULEINFO()
        if psapi.GetModuleInformation(ph, mods[i], C.byref(mi), C.sizeof(mi)):
            out.append((int(mi.lpBaseOfDll or 0), int(mi.lpBaseOfDll or 0) + mi.SizeOfImage,
                        "#%d" % i))
    k32.CloseHandle(ph)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=300)
    ap.add_argument("--interval", type=float, default=0.002)
    args = ap.parse_args()

    tid = game_tid()
    try:
        import threadcpu
        pid = threadcpu.find_pid()
        if isinstance(pid, (list, tuple)):
            pid = pid[0] if pid else 0
    except Exception:
        pid = 0
    if not tid or not pid:
        print("не найден сервер (tid=%d pid=%d)" % (tid, pid))
        return 1

    con = sqlite3.connect(r"C:\Dev\_research\v361.sqlite")
    rows = con.execute("SELECT rva, name, size FROM fn WHERE tag=5 ORDER BY rva").fetchall()
    con.close()
    rvas = [r for r, n, s in rows]
    info = [(n, s if s > 0 else 0x40) for r, n, s in rows]

    def look(rva):
        i = bisect.bisect_right(rvas, rva) - 1
        if i >= 0 and rva < rvas[i] + info[i][1]:
            return info[i][0]
        return None

    h = k32.OpenThread(THREAD_SUSPEND_RESUME | THREAD_GET_CONTEXT | THREAD_QUERY_INFORMATION,
                       False, tid)
    if not h:
        print("OpenThread не удался")
        return 2
    ph = k32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)

    mods = module_map(pid)
    game = [m for m in mods if m[2] == "#0"]  # основной модуль идёт первым

    chains = {}
    kinds = {}
    total = 0
    rip_hist = {}
    # CONTEXT обязан быть выровнен по 16 байт, иначе GetThreadContext
    # возвращает TRUE, но не заполняет буфер (RIP читается как 0).
    raw_ctx = C.create_string_buffer(CONTEXT_SIZE + 16)
    ctx_addr = (C.addressof(raw_ctx) + 15) & ~15
    t0 = time.time()
    while total < args.samples and time.time() - t0 < 900:
        struct.pack_into("<I", raw_ctx, OFF_FLAGS_X64, CONTEXT_ALL)
        if k32.SuspendThread(h) == 0xFFFFFFFF:
            break
        ok = k32.GetThreadContext(h, C.c_void_p(ctx_addr))
        k32.ResumeThread(h)
        if not ok:
            break
        total += 1
        rip = struct.unpack_from("<Q", raw_ctx, OFF_RIP_X64)[0]
        rsp = struct.unpack_from("<Q", raw_ctx, OFF_RSP_X64)[0]
        key = None
        for s, e, n in mods:
            if s <= rip < e:
                key = "модуль %s" % n
                break
        if key is None:
            key = "ЯДРО (системный вызов)" if rip > 0x7FF000000000 else "вне модулей"
        kinds[key] = kinds.get(key, 0) + 1
        rip_hist[rip & ~0xFFFF] = rip_hist.get(rip & ~0xFFFF, 0) + 1

        if key != "ЯДРО (системный вызов)":
            time.sleep(args.interval)
            continue

        # стек: ищем адреса, попавшие в основной модуль игры
        raw = C.create_string_buffer(8 * STACK_DEPTH)
        got = C.c_size_t()
        chain = []
        if k32.ReadProcessMemory(ph, C.c_void_p(rsp), raw, 8 * STACK_DEPTH, C.byref(got)):
            base = game[0][0] if game else 0
            limit = game[0][1] if game else 0
            for i in range(min(STACK_DEPTH, got.value // 8)):
                w = struct.unpack_from("<Q", raw, i * 8)[0]
                if base < w < limit:
                    nm = look(w - base)
                    if nm and (not chain or chain[-1] != nm):
                        chain.append(nm)
        ck = " <- ".join(chain[:6]) if chain else "<стек без кадров игры>"
        chains[ck] = chains.get(ck, 0) + 1
        time.sleep(args.interval)

    k32.CloseHandle(h)
    k32.CloseHandle(ph)

    print("сэмплов %d\n" % total)
    print("=== где находился RIP ===")
    for k, c in sorted(kinds.items(), key=lambda kv: -kv[1]):
        print("   %5.1f%%  %s" % (100.0 * c / max(total, 1), k))
    tot_kernel = kinds.get("ЯДРО (системный вызов)", 0)
    if tot_kernel:
        print("\n=== цепочки вызовов, ведущие к системному вызову ===")
        for ck, c in sorted(chains.items(), key=lambda kv: -kv[1])[:12]:
            print("   %5.1f%%  %s" % (100.0 * c / tot_kernel, ck[:160]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
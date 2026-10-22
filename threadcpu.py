# -*- coding: utf-8 -*-
"""
Captures the per-thread CPU breakdown of a live ShooterGameServer.

UE4 threads are named via SetThreadDescription (GameThread, TaskGraphThread N,
PhysicsThread, ...), so names are taken from Windows, not from the PDB.

    python threadcpu.py [--pid N] [--seconds 30] [--interval 1.0]
"""
import argparse
import ctypes as C
from ctypes import wintypes as W

k32 = C.WinDLL("kernel32", use_last_error=True)

TH32CS_SNAPTHREAD = 0x00000004
MAXIMUM_THREADS = 2048
INVALID_HANDLE_VALUE = W.HANDLE(-1).value


class THREADENTRY32(C.Structure):
    _fields_ = [
        ("dwSize", W.DWORD),
        ("cntUsage", W.DWORD),
        ("th32ThreadID", W.DWORD),
        ("th32OwnerProcessID", W.DWORD),
        ("tpBasePri", W.LONG),
        ("tpDeltaPri", W.LONG),
        ("dwFlags", W.DWORD),
    ]


class FILETIME(C.Structure):
    _fields_ = [("dwLowDateTime", W.DWORD), ("dwHighDateTime", W.DWORD)]


k32.CreateToolhelp32Snapshot.restype = W.HANDLE
k32.CreateToolhelp32Snapshot.argtypes = [W.DWORD, W.DWORD]
k32.Thread32First.argtypes = [W.HANDLE, C.POINTER(THREADENTRY32)]
k32.Thread32Next.argtypes = [W.HANDLE, C.POINTER(THREADENTRY32)]
k32.OpenThread.argtypes = [W.DWORD, W.BOOL, W.DWORD]
k32.OpenThread.restype = W.HANDLE
k32.GetThreadTimes.argtypes = [W.HANDLE, C.POINTER(FILETIME), C.POINTER(FILETIME),
                               C.POINTER(FILETIME), C.POINTER(FILETIME)]
k32.GetThreadDescription.argtypes = [W.HANDLE, C.POINTER(W.LPWSTR)]
k32.GetThreadDescription.restype = C.c_long
k32.LocalFree.argtypes = [W.HLOCAL]

kernel32 = k32
THREAD_QUERY_LIMITED_INFORMATION = 0x0800
THREAD_QUERY_INFORMATION = 0x0040


def find_pid(name="ShooterGameServer.exe"):
    # without psutil: Toolhelp over processes
    TH32CS_SNAPPROCESS = 0x00000002

    class PROCESSENTRY32(C.Structure):
        _fields_ = [
            ("dwSize", W.DWORD), ("cntUsage", W.DWORD), ("th32ProcessID", W.DWORD),
            ("th32DefaultHeapID", C.c_size_t), ("th32ModuleID", W.DWORD),
            ("cntThreads", W.DWORD), ("th32ParentProcessID", W.DWORD),
            ("pcPriClassBase", W.LONG), ("dwFlags", W.DWORD),
            ("szExeFile", W.WCHAR * 260),
        ]

    k32.CreateToolhelp32Snapshot.restype = W.HANDLE
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == INVALID_HANDLE_VALUE:
        raise SystemExit("snapshot failed")
    pe = PROCESSENTRY32()
    pe.dwSize = C.sizeof(pe)
    found = []
    if k32.Process32FirstW(snap, C.byref(pe)):
        while True:
            if pe.szExeFile.lower() == name.lower():
                found.append(pe.th32ProcessID)
            if not k32.Process32NextW(snap, C.byref(pe)):
                break
    k32.CloseHandle(snap)
    return found


def threads_of(pid):
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0)
    out = []
    te = THREADENTRY32()
    te.dwSize = C.sizeof(te)
    if k32.Thread32First(snap, C.byref(te)):
        while True:
            if te.th32OwnerProcessID == pid:
                out.append(te.th32ThreadID)
            if not k32.Thread32Next(snap, C.byref(te)):
                break
    k32.CloseHandle(snap)
    return out


def thread_name(tid):
    h = k32.OpenThread(THREAD_QUERY_LIMITED_INFORMATION, False, tid)
    if not h:
        return "?"
    desc = W.LPWSTR()
    name = "?"
    if k32.GetThreadDescription(h, C.byref(desc)) == 0 and desc:
        name = desc.value or "?"
        k32.LocalFree(desc)
    k32.CloseHandle(h)
    return name


def cpu_times(tid):
    h = k32.OpenThread(THREAD_QUERY_LIMITED_INFORMATION, False, tid)
    if not h:
        return None
    c, e, k, u = FILETIME(), FILETIME(), FILETIME(), FILETIME()
    ok = k32.GetThreadTimes(h, C.byref(c), C.byref(e), C.byref(k), C.byref(u))
    k32.CloseHandle(h)
    if not ok:
        return None
    k100 = (k.dwHighDateTime << 32) | k.dwLowDateTime
    u100 = (u.dwHighDateTime << 32) | u.dwLowDateTime
    return (k100 + u100) / 1e7  # CPU seconds


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, default=0)
    ap.add_argument("--seconds", type=float, default=30.0)
    ap.add_argument("--interval", type=float, default=1.0)
    args = ap.parse_args()

    pid = args.pid or (find_pid() or [None])[0]
    if not pid:
        raise SystemExit("ShooterGameServer.exe not found")
    print("pid=%d" % pid, flush=True)

    tids = threads_of(pid)
    names = {t: thread_name(t) for t in tids}
    base = {t: cpu_times(t) for t in tids}
    import time

    time.sleep(args.interval)
    samples = []
    n = max(1, int(args.seconds / args.interval))
    for i in range(n):
        time.sleep(args.interval)
        cur = {}
        for t in tids:
            v = cpu_times(t)
            if v is None:
                continue
            b = base.get(t)
            if b is not None:
                cur[t] = v - b
            else:
                base[t] = v
        samples.append(cur)

    # average over the window
    span = args.seconds or 1.0
    rows = []
    for t in tids:
        vals = [s.get(t, 0.0) for s in samples]
        if not vals:
            continue
        cpu = sum(vals) / len(vals) if vals else 0.0
        pct = 100.0 * cpu / span
        rows.append((cpu, pct, t, names.get(t, "?")))
    rows.sort(reverse=True)

    print("\n%-16s %6s %8s  %s" % ("thread", "cpu_s/s", "%core", "tid"))
    print("-" * 60)
    total = 0.0
    for cpu, pct, t, nm in rows:
        total += pct
        if cpu < 0.001:
            continue
        print("%-16s %6.2f %7.1f%%  %d" % (nm[:16], cpu, pct, t))
    print("-" * 60)
    print("threads: %d, total cores busy: %.2f" % (len(rows), total))


if __name__ == "__main__":
    main()
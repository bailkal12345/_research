# -*- coding: utf-8 -*-
"""Печатает список модулей процесса (нужно, чтобы проверить, что плагин загружен)."""
import ctypes as C
from ctypes import wintypes as W
import sys

k32 = C.WinDLL("kernel32", use_last_error=True)
psapi = C.WinDLL("psapi", use_last_error=True)

TH32CS_SNAPMODULE = 0x00000008
TH32CS_SNAPMODULE32 = 0x00000010
LIST_MODULES_ALL = 0x03


class MODULEENTRY32W(C.Structure):
    _fields_ = [
        ("dwSize", W.DWORD), ("th32ModuleID", W.DWORD), ("th32ProcessID", W.DWORD),
        ("GlblcntUsage", W.DWORD), ("ProccntUsage", W.DWORD),
        ("modBaseAddr", C.POINTER(C.c_ubyte)), ("modBaseSize", W.DWORD),
        ("hModule", W.HMODULE), ("szModule", W.WCHAR * 256), ("szExePath", W.WCHAR * 260),
    ]


k32.CreateToolhelp32Snapshot.restype = W.HANDLE
psapi.GetModuleFileNameExW.argtypes = [W.HANDLE, W.HMODULE, W.LPWSTR, W.DWORD]


def modules(pid):
    out = []
    for flags in (LIST_MODULES_ALL,):
        snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | flags, pid)
        if snap == W.HANDLE(-1).value:
            continue
        me = MODULEENTRY32W()
        me.dwSize = C.sizeof(me)
        if k32.Module32FirstW(snap, C.byref(me)):
            while True:
                out.append((me.szModule, me.szExePath))
                if not k32.Module32NextW(snap, C.byref(me)):
                    break
        k32.CloseHandle(snap)
    return out


if __name__ == "__main__":
    pid = int(sys.argv[1])
    needle = sys.argv[2].lower() if len(sys.argv) > 2 else ""
    for name, path in modules(pid):
        if needle and needle not in name.lower() and needle not in path.lower():
            continue
        print("%-34s %s" % (name, path))
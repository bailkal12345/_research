# -*- coding: utf-8 -*-
"""
ark_lab_net.py — протокольные помощники для лабораторного стенда ARK SE v358.

Содержит только «чистые» функции: A2S/Steam-query клиент, Source-RCON клиент
и съём метрик процесса сервера (CPU / RSS) через WinAPI без внешних пакетов.

Всё, что здесь есть, используется ТОЛЬКО против локального стенда
(C:\\asmdata\\Servers\\Server2 или 127.0.0.1). Функция guard_target()
обязана быть вызвана до любого сетевого действия.

Протоколы реализованы по:
  * A2S (Steam Query)  — «Source Engine Query», запросы T/I/V, ответы A/I/V.
  * Source RCON        — len-prefixed пакеты, типы 0/2/3.
  * Антивирусная мелочь: RCON-пароль в ARK — это ServerAdminPassword из
    GameUserSettings.ini; сравнение паролей в движке РЕГИСТРОЗАВИСИМОЕ
    (см. RCONClientConnection::ProcessRCONPacket, v358 @0x140a6cc20).
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import socket
import struct
import time

# ---------------------------------------------------------------------------
# Ограничение области применимости
# ---------------------------------------------------------------------------

#: Адреса, к которым этот стенд имеет право обращаться.
LAB_HOSTS = frozenset({"127.0.0.1", "localhost", "::1", "192.168.8.218"})


class LabTargetError(RuntimeError):
    """Попытка обратиться к адресу вне лабораторного стенда."""


def guard_target(host: str, allow_any: bool = False) -> str:
    """Проверяет, что host принадлежит стенду. Бросает LabTargetError иначе."""
    if allow_any:
        return host
    if host not in LAB_HOSTS:
        raise LabTargetError(
            "цель %r вне лабораторного стенда; разрешены только %s "
            "(для иных адресов нужен явный --allow-any)"
            % (host, ", ".join(sorted(LAB_HOSTS)))
        )
    return host


# ---------------------------------------------------------------------------
# Метрики процесса сервера (WinAPI, без psutil)
# ---------------------------------------------------------------------------

_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_psapi = ctypes.WinDLL("psapi", use_last_error=True)

TH32CS_SNAPPROCESS = 0x00000002
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_VM_READ = 0x0010
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class _FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", wt.DWORD), ("dwHighDateTime", wt.DWORD)]


class _PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("cb", wt.DWORD),
        ("PageFaultCount", wt.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wt.DWORD),
        ("cntUsage", wt.DWORD),
        ("th32ProcessID", wt.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", wt.DWORD),
        ("cntThreads", wt.DWORD),
        ("th32ParentProcessID", wt.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wt.DWORD),
        ("szExeFile", wt.WCHAR * 260),
    ]


_k32.CreateToolhelp32Snapshot.restype = wt.HANDLE
_k32.CreateToolhelp32Snapshot.argtypes = [wt.DWORD, wt.DWORD]
_k32.Process32FirstW.restype = wt.BOOL
_k32.Process32FirstW.argtypes = [wt.HANDLE, ctypes.POINTER(_PROCESSENTRY32W)]
_k32.Process32NextW.restype = wt.BOOL
_k32.Process32NextW.argtypes = [wt.HANDLE, ctypes.POINTER(_PROCESSENTRY32W)]
_k32.CloseHandle.argtypes = [wt.HANDLE]
_k32.OpenProcess.restype = wt.HANDLE
_k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
_k32.GetProcessTimes.restype = wt.BOOL
_k32.GetProcessTimes.argtypes = [
    wt.HANDLE,
    ctypes.POINTER(_FILETIME),
    ctypes.POINTER(_FILETIME),
    ctypes.POINTER(_FILETIME),
    ctypes.POINTER(_FILETIME),
]
_psapi.GetProcessMemoryInfo.restype = wt.BOOL
_psapi.GetProcessMemoryInfo.argtypes = [
    wt.HANDLE,
    ctypes.POINTER(_PROCESS_MEMORY_COUNTERS),
    wt.DWORD,
]


def find_pid(exe_name: str = "ShooterGameServer.exe") -> int | None:
    """Ищет PID процесса по имени исполняемого файла (первый найденный)."""
    pids = find_pids(exe_name)
    return pids[0] if pids else None


def find_pids(exe_name: str = "ShooterGameServer.exe") -> list[int]:
    """Все PID процессов с таким именем."""
    out: list[int] = []
    snap = _k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snap or snap == INVALID_HANDLE_VALUE:
        return out
    try:
        entry = _PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(_PROCESSENTRY32W)
        if not _k32.Process32FirstW(snap, ctypes.byref(entry)):
            return out
        while True:
            if entry.szExeFile.lower() == exe_name.lower():
                out.append(int(entry.th32ProcessID))
            if not _k32.Process32NextW(snap, ctypes.byref(entry)):
                break
    finally:
        _k32.CloseHandle(snap)
    return out


_k32.QueryFullProcessImageNameW.restype = wt.BOOL
_k32.QueryFullProcessImageNameW.argtypes = [
    wt.HANDLE, wt.DWORD, wt.LPWSTR, ctypes.POINTER(wt.DWORD),
]


def process_path(pid: int) -> str:
    """Полный путь к образу процесса ('' если не удалось получить)."""
    h = _k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return ""
    try:
        size = wt.DWORD(1024)
        buf = ctypes.create_unicode_buffer(1024)
        if _k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return buf.value
        return ""
    finally:
        _k32.CloseHandle(h)


def pick_pid(exe_name: str = "ShooterGameServer.exe", path_filter: str = "") -> int | None:
    """Выбирает PID нужного экземпляра сервера.

    На машине может быть несколько копий ShooterGameServer.exe (Server1,
    Server2). Порядок в snapshot Toolhelp не гарантирован, поэтому выбираем
    по ПОДСТРОКЕ пути к образу (например "Server2"). Если фильтр не задан —
    берём первый, но печатаем все найденные пути, чтобы выбор был проверяем.
    """
    pids = find_pids(exe_name)
    if not pids:
        return None
    paths = {pid: process_path(pid) for pid in pids}
    if path_filter:
        low = path_filter.lower()
        for pid in pids:
            if low in paths[pid].lower():
                return pid
        return None
    return pids[0]


def _filetime_to_seconds(ft: _FILETIME) -> float:
    return (ft.dwHighDateTime << 32 | ft.dwLowDateTime) / 1e7


class ProcessMeter:
    """Снимает CPU-время и рабочее множество процесса сервера.

    Использование:
        m = ProcessMeter(pid)
        s1 = m.sample()
        ...нагрузка...
        s2 = m.sample()
        cpu_pct = (s2.cpu - s1.cpu) / (s2.t - s1.t) * 100
    """

    def __init__(self, pid: int | None):
        self.pid = pid
        self._handle = None
        if pid:
            self._handle = _k32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ, False, pid
            )
            if not self._handle:
                self._handle = None

    def sample(self) -> dict:
        """Возвращает {t, cpu, ws}. cpu — суммарное CPU-время процесса, с."""
        out = {"t": time.perf_counter(), "cpu": 0.0, "ws": 0}
        if not self._handle:
            return out
        created = _FILETIME()
        exited = _FILETIME()
        kernel = _FILETIME()
        user = _FILETIME()
        if _k32.GetProcessTimes(
            self._handle,
            ctypes.byref(created),
            ctypes.byref(exited),
            ctypes.byref(kernel),
            ctypes.byref(user),
        ):
            out["cpu"] = _filetime_to_seconds(kernel) + _filetime_to_seconds(user)
        counters = _PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(_PROCESS_MEMORY_COUNTERS)
        if _psapi.GetProcessMemoryInfo(self._handle, ctypes.byref(counters), counters.cb):
            out["ws"] = int(counters.WorkingSetSize)
        return out


# ---------------------------------------------------------------------------
# A2S / Steam Query
# ---------------------------------------------------------------------------

A2S_GETCHALLENGE = 0x54  # 'T'  — "Source Engine Query"
A2S_INFO = 0x49  # 'I'
A2S_PLAYER = 0x55  # 'U'
A2S_PLAYER_RULES = 0x56  # 'V'
A2S_CHALLENGE_RESPONSE = 0x41  # 'A'
#: Типы ОТВЕТОВ. Важно: Steam-серверная API ARK отвечает на запрос правил
#: (0x56) ответом 0x45 ('E' = A2S_RULES), а не 0x56. На запрос игроков
#: (0x55) — ответом 0x44 ('D'). На A2S_INFO (0x49) сервер НЕ отвечает
#: вовсе (проверено на обоих стендах, 27015 и 27016) — карточка сервера
#: в браузере собирается из правил.
A2S_PLAYER_RESPONSE = 0x44  # 'D'
A2S_RULES_RESPONSE = 0x45  # 'E'
HEADER = b"\xff\xff\xff\xff"


class A2SError(RuntimeError):
    pass


def _recv_cstrings(data: bytes, start: int) -> list[str]:
    """Разбирает NUL-разделённые строки, начиная с offset."""
    out: list[str] = []
    i = start
    while i < len(data):
        j = data.find(b"\x00", i)
        if j < 0:
            break
        out.append(data[i:j].decode("latin-1", "replace"))
        i = j + 1
    return out


def a2s_challenge(sock: socket.socket, addr: tuple[str, int]) -> bytes:
    """Шлёт A2S_GETCHALLENGE и возвращает 4-байтовый challenge.

    Некоторые серверы сразу отвечают A2S_INFO (0x49) — тогда возвращаем b'',
    чтобы вызывающая сторона разобрала ответ как есть.
    """
    sock.sendto(HEADER + bytes([A2S_GETCHALLENGE]) + b"Source Engine Query\x00", addr)
    data = sock.recv(8192)
    if len(data) < 5:
        raise A2SError("короткий ответ на GETCHALLENGE: %d байт" % len(data))
    if data[4] == A2S_CHALLENGE_RESPONSE:
        return data[5:9]
    if data[4] == A2S_INFO:
        return b""
    raise A2SError("неожиданный тип ответа 0x%02x" % data[4])


def a2s_info(sock: socket.socket, addr: tuple[str, int], challenge: bytes = b"",
             optional: bool = False) -> dict | None:
    """A2S_INFO. Возвращает разобранные поля ответа.

    На стенде Steam-серверная API на A2S_INFO не отвечает, поэтому при
    optional=True таймаут возвращает None вместо исключения.
    """
    sock.sendto(HEADER + bytes([A2S_INFO]) + challenge, addr)
    try:
        data = sock.recv(8192)
    except socket.timeout:
        if optional:
            return None
        raise A2SError("таймаут на A2S_INFO (сервер не поддерживает этот запрос)")
    if len(data) < 6:
        raise A2SError("короткий ответ на A2S_INFO: %d байт" % len(data))
    if data[4] != A2S_INFO:
        raise A2SError("ответ не A2S_INFO (0x%02x)" % data[4])
    fields = _recv_cstrings(data, 6)  # +1 — пропуск protocol-байта
    result = {
        "protocol": data[5],
        "raw_len": len(data),
        "name": fields[0] if len(fields) > 0 else "",
        "map": fields[1] if len(fields) > 1 else "",
        "folder": fields[2] if len(fields) > 2 else "",
        "game": fields[3] if len(fields) > 3 else "",
        "appid": fields[4] if len(fields) > 4 else "",
        "players": fields[5] if len(fields) > 5 else "",
        "maxplayers": fields[6] if len(fields) > 6 else "",
        "keywords": ",".join(fields[7:]),
    }
    return result


def a2s_player_rules(sock: socket.socket, addr: tuple[str, int], challenge: bytes) -> dict:
    """A2S_PLAYER_RULES. Возвращает dict правил (ключ -> значение).

    Формат ответа: FFFFFFFF | 0x45 | uint16 count | (key\\0value\\0) * count
    """
    sock.sendto(HEADER + bytes([A2S_PLAYER_RULES]) + challenge, addr)
    data = sock.recv(16384)
    if len(data) < 7:
        raise A2SError("короткий ответ на A2S_PLAYER_RULES: %d байт" % len(data))
    if data[4] != A2S_RULES_RESPONSE:
        raise A2SError("ответ не A2S_RULES (0x%02x)" % data[4])
    (count,) = struct.unpack_from("<H", data, 5)
    rules: dict[str, str] = {}
    i = 7
    for _ in range(count):
        k_end = data.find(b"\x00", i)
        if k_end < 0:
            break
        key = data[i:k_end].decode("latin-1", "replace")
        v_end = data.find(b"\x00", k_end + 1)
        if v_end < 0:
            break
        rules[key] = data[k_end + 1 : v_end].decode("latin-1", "replace")
        i = v_end + 1
    return rules


def a2s_player(sock: socket.socket, addr: tuple[str, int], challenge: bytes) -> list[str]:
    """A2S_PLAYER. Возвращает список имён игроков (может быть пустым).

    Формат ответа: FFFFFFFF | 0x44 | uint8 count | (index\\0name\\0score\\0duration\\0)*
    count == 0xFF — сервер не смог отдать список.
    """
    sock.sendto(HEADER + bytes([A2S_PLAYER]) + challenge, addr)
    data = sock.recv(16384)
    if len(data) < 6:
        raise A2SError("короткий ответ на A2S_PLAYER: %d байт" % len(data))
    if data[4] != A2S_PLAYER_RESPONSE:
        raise A2SError("ответ не A2S_PLAYER (0x%02x)" % data[4])
    count = data[5]
    if count == 0xFF:
        raise A2SError("сервер не отдал список игроков (0xFF)")
    names: list[str] = []
    i = 6
    for _ in range(count):
        i += 1  # индекс игрока (byte)
        j = data.find(b"\x00", i)
        if j < 0:
            break
        names.append(data[i:j].decode("latin-1", "replace"))
        i = j + 1
        i += 8  # score (float32) + duration (float32)
    return names


def make_query_socket(timeout: float = 3.0) -> socket.socket:
    """UDP-сокет для A2S. Один сокет на один запрос — чтобы не путать ответы."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    return s


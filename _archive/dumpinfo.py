# -*- coding: utf-8 -*-
"""
Разбор минидампа Windows: код исключения, адрес, поток, образ модуля.

    python dumpinfo.py <файл.dmp>

Формат MDMP разбирается напрямую (без внешних зависимостей):
  header: 'MDMP'(4) version(4) nstreams(4) dir_rva(4) checksum(4) timestamp(4) flags(8)
  каталог: nstreams * {type(4) size(4) rva(4)}
  stream 6 (ExceptionStream): tid(4) pad(4) ExceptionCode(4) flags(4)
      ExceptionRecord(8) ExceptionAddress(8) nparams(4) pad(4) info[15](8*15)
      затем MINIDUMP_LOCATION_DESCRIPTOR{size(4) rva(4)} для контекста
  stream 4 (ModuleList): count(4) + {BaseOfImage(8) SizeOfImage(4) CheckSum(4)
      TimeDateStamp(4) ModuleNameRva(4)}
      имя = MINIDUMP_STRING{len(4) utf16le[len]}
  stream 3 (ThreadList): count(4) + {tid(4) suspend(4) prio_class(4) prio(4)
      teb(8) stack{MemoryDescriptor{size(4) rva(4)}} ctx{size(4) rva(4)}}
"""
import struct
import sys

STREAM = {3: "ThreadList", 4: "ModuleList", 5: "MemoryList", 6: "Exception",
          7: "SystemInfo", 8: "ThreadExList", 9: "Memory64List",
          10: "CommentA", 11: "CommentW", 15: "FunctionTable", 16: "UnloadedModuleList"}

CODES = {0xC0000005: "ACCESS_VIOLATION", 0xC000001D: "ILLEGAL_INSTRUCTION",
         0xC0000094: "INTEGER_DIVIDE_BY_ZERO", 0xC0000006: "STATUS_IN_PAGE_ERROR",
         0xC0000374: "HEAP_CORRUPTION", 0x80000003: "BREAKPOINT",
         0x80000004: "SINGLE_STEP", 0xC0000135: "DLL_NOT_FOUND",
         0xC0000138: "ORDINAL_NOT_FOUND", 0xC0000139: "ENTRYPOINT_NOT_FOUND",
         0xC0000409: "STACK_BUFFER_OVERRUN", 0xC0000602: "FAIL_FAST_EXCEPTION",
         0xE06D7363: "CPP_EXCEPTION", 0x80000001: "GUARD_VIOLATION"}


def mn(x):
    return (x & 0xFFFFFFFF).to_bytes(4, "little")


def u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


def u64(b, o):
    return struct.unpack_from("<Q", b, o)[0]


def main(path):
    with open(path, "rb") as f:
        d = f.read()
    if d[:4] != b"MDMP":
        print("не MDMP:", d[:4])
        return 2
    n = u32(d, 8)
    dir_rva = u32(d, 12)
    print("файл: %s, %d байт, потоков-каталогов %d" % (path, len(d), n))

    streams = {}
    for i in range(n):
        o = dir_rva + i * 12
        st, size, rva = u32(d, o), u32(d, o + 4), u32(d, o + 8)
        streams.setdefault(st, (size, rva))

    # ---- исключение
    if 6 in streams:
        _, r = streams[6]
        tid = u32(d, r)
        code = u32(d, r + 8)
        addr = u64(d, r + 24)
        print("\nИСКЛЮЧЕНИЕ")
        print("  поток          : %d" % tid)
        print("  код            : 0x%08X %s" % (code, CODES.get(code, "?")))
        print("  адрес          : 0x%016X" % addr)
    else:
        print("\nпотока ExceptionStream нет — это не аварийный дамп")
        tid = None

    # ---- модули
    if 4 in streams:
        _, r = streams[4]
        cnt = u32(d, r)
        mods = []
        for i in range(cnt):
            # MINIDUMP_MODULE = 108 байт (VersionInfo 52 + Cv/Misc/Reserved)
            o = r + 4 + i * 108
            base, size, name_rva = u64(d, o), u32(d, o + 8), u32(d, o + 20)
            ln = u32(d, name_rva)
            nm = d[name_rva + 4:name_rva + 4 + ln].decode("utf-16-le", "replace")
            mods.append((base, base + size, nm))
        print("\nМОДУЛИ (%d)" % cnt)
        for b0, b1, nm in mods:
            print("  0x%016X-0x%016X  %s" % (b0, b1, nm))
        if "addr" in dir():
            for b0, b1, nm in mods:
                if b0 <= addr < b1:
                    print("\nАДРЕС ИСКЛЮЧЕНИЯ В МОДУЛЕ: %s, смещение 0x%X" % (nm, addr - b0))
                    break
        return 0

    print("\nсписок модулей отсутствует — определить модуль нельзя")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else
                  r"C:\asmdata\Servers\Server1\ShooterGame\Saved\Logs\Dump-490729840.dmp"))
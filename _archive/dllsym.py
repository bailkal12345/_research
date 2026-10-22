# -*- coding: utf-8 -*-
"""По RVA внутри внешней DLL находит ближайший экспорт (для ntdll/PhysX/MSVCR)."""
import struct
import sys


def exports(path):
    with open(path, "rb") as f:
        data = f.read()
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    machine, nsec = struct.unpack_from("<HH", data, pe + 4)
    opt_size = struct.unpack_from("<H", data, pe + 20)[0]
    opt = pe + 24
    magic = struct.unpack_from("<H", data, opt)[0]
    dd = opt + (112 if magic == 0x20B else 96)
    exp_rva, exp_size = struct.unpack_from("<II", data, dd)
    secs = []
    so = pe + 24 + opt_size
    for i in range(nsec):
        b = so + i * 40
        vaddr, vsize, raddr, rsize = struct.unpack_from("<IIII", data, b + 8)
        secs.append((vaddr, vsize, raddr, rsize))

    def r2o(rva):
        for vaddr, vsize, raddr, rsize in secs:
            if vaddr <= rva < vaddr + max(vsize, rsize):
                return raddr + (rva - vaddr)
        return None

    exp_off = r2o(exp_rva)
    (_, _, _, _, name_rva, ordinal_base, nfuncs, nnames, funcs_rva, names_rva, ords_rva) = struct.unpack_from(
        "<IIHHIIIIIII", data, exp_off
    )
    dll_name_off = r2o(name_rva)
    dll_name = data[dll_name_off:data.index(b"\0", dll_name_off)].decode()

    table = []
    names_off = r2o(names_rva)
    ords_off = r2o(ords_rva)
    funcs_off = r2o(funcs_rva)
    for i in range(nnames):
        nrva = struct.unpack_from("<I", data, names_off + 4 * i)[0]
        noff = r2o(nrva)
        name = data[noff:data.index(b"\0", noff)].decode()
        ord_idx = struct.unpack_from("<H", data, ords_off + 2 * i)[0]
        frva = struct.unpack_from("<I", data, funcs_off + 4 * ord_idx)[0]
        if frva:
            table.append((frva, name))
    table.sort()
    return dll_name, table


def main():
    path = sys.argv[1]
    rva = int(sys.argv[2], 16)
    dll_name, table = exports(path)
    best = None
    for addr, name in table:
        if addr <= rva:
            best = (addr, name)
        else:
            break
    print("%s +0x%X" % (dll_name, rva))
    if best:
        print("  ближайший экспорт: %s+0x%X (смещение +0x%X)" % (best[1], best[0], rva - best[0]))
    else:
        print("  экспортов ниже адреса нет")


if __name__ == "__main__":
    main()
import sys, os, struct
from minidump.minidumpfile import MinidumpFile

path = sys.argv[1]
targets = []
for a in sys.argv[2:]:
    if a.lower().startswith("0x"):
        targets.append(int(a, 16))
    else:
        m = __import__("re").match(r"([0-9a-fA-F]+):([0-9]+)?", a)
        # form base:delta — относительный адрес в регионе (форвард/назад)
        if m:
            targets.append((m.group(1).lower(), int(m.group(2) or 0)))
        else:
            targets.append(int(a, 16))

mdf = MinidumpFile.parse(path)
# модули
try:
    mods = [(m.baseaddress, m.size, os.path.basename(str(m.name or "?"))) for m in mdf.modules.modules]
except Exception:
    mods = []

def resolve(addr):
    for base, size, name in mods:
        if base <= addr < base + size:
            return f"{name}+0x{addr-base:X}"
    return None

segs = mdf.memory_segments_64.memory_segments
ranges = []
for s in segs:
    ranges.append((s.start_virtual_address, s.start_virtual_address + s.size, s.start_virtual_address))
ranges.sort()

# классификация каждого target: соседние committed-диапазоны за/до, длина сплошного коммита
def scan(target):
    # найти диапазон-хост
    host = None
    # сформировать абсолютный адрес
    base = None
    if isinstance(target, tuple):
        base = next((b for b, e, _ in ranges if b <= int(target[0], 16) < e), None)
        if base is None:
            # base как модуль?
            for b, e, _ in ranges:
                pass
        if base is None:
            for mbase, msize, name in mods:
                if str(name).lower().startswith("engineswap"):
                    base = mbase + target[1]
        if base is None:
            print("can't resolve", target)
            return
    else:
        base = target

    # host range
    host = None
    for s, e, _ in ranges:
        if s <= base < e:
            host = (s, e)
            break
    # сплошной до/после
    total = 0
    if host:
        lo, hi = host[0], host[1]
        # расширение вниз
        changed = True
        while changed:
            changed = False
            for s, e, _ in ranges:
                if e == lo:
                    lo = s; changed = True
        changed = True
        while changed:
            changed = False
            for s, e, _ in ranges:
                if s == hi:
                    hi = e; changed = True
        total = hi - lo
    print(f"target 0x{base:X} host={(hex(host[0]), hex(host[1])) if host else None} "
          f"contiguous={( total/1024/1024):.1f} MiB mod={resolve(base) or '-'}")
    # читаем 64 байта
    reader = mdf.get_reader()
    try:
        data = reader.read(base, 64)
        vals = struct.unpack("<8Q", data)
        print("   first64:", " ".join(resolve(v) or f"0x{v:X}" for v in vals))
    except Exception as e:
        print("   first64 unreadable:", e)

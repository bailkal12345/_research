import sys
from minidump.minidumpfile import MinidumpFile

path = sys.argv[1]
mdf = MinidumpFile.parse(path)
mods = [(m.baseaddress, m.size, __import__("os").path.basename(str(m.name or "?"))) for m in mdf.modules.modules]

def resolve(addr):
    for base, size, name in mods:
        if base <= addr < base + size:
            return f"{name}+0x{addr-base:X}"
    return f"0x{addr:X}"

es = mdf.exception
if es is None:
    print("no exception stream")
else:
    rec = es.exception_record
    print("exception thread:", es.thread_id)
    print("code:", hex(rec.ExceptionCode))
    print("fault addr:", hex(rec.ExceptionInformation[1] if rec.ExceptionInformation else 0))
    print("rip (context):", hex(es.context.Rip if hasattr(es, 'context') else 0))
    for i, a in enumerate(rec.ExceptionAddress, start=0):
        try:
            print(f"  addr[{i}]", hex(a), resolve(a))
        except Exception as e:
            break
    print("module of exception address:", resolve(rec.ExceptionAddress[0] if isinstance(rec.ExceptionAddress, list) else rec.ExceptionAddress))

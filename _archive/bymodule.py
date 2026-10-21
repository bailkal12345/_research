import collections, struct, sys, os, glob
sys.path.insert(0, ".")
from symbolize import FuncTable

PDIR = r"C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi\Plugins\TickProf"
# аргумент — конкретный профиль, иначе берём самый свежий
cands = sorted(glob.glob(os.path.join(PDIR, "prof_*.bin")), key=os.path.getmtime)
binp = sys.argv[1] if len(sys.argv) > 1 else cands[-1]
print("профиль:", os.path.basename(binp))
with open(binp, "rb") as f:
    base, count = struct.unpack("<QQ", f.read(16))
    rips = struct.unpack("<%dQ" % count, f.read(8*count))

mods = []
mp = binp.rsplit(".",1)[0] + ".modules.txt"
for line in open(mp, encoding="utf-8", errors="replace").read().splitlines()[1:]:
    p = line.split("\t")
    if len(p) >= 3:
        s = int(p[0],16); mods.append((s, s+int(p[1],16), p[2].split("\\")[-1]))
mods.sort()

def in_mod(a):
    for s,e,n in mods:
        if s <= a < e:
            return n
    return None

tbl = FuncTable(r"C:\Dev\_research\v361.sqlite")
by_mod = collections.Counter()
by_cls = collections.Counter()
idle = 0
for rip in rips:
    m = in_mod(rip)
    if m is None:
        by_mod["<вне всех модулей>"] += 1
        continue
    if m.lower() == "ntdll.dll":
        off = rip - next(s for s,_,n in mods if n=="ntdll.dll")
        if 0x15E000 <= off <= 0x160000:
            idle += 1
            continue
    by_mod[m] += 1
    if m.lower() == "shootergameserver.exe":
        nm = tbl.lookup(rip - base)
        if nm:
            c = nm[:nm.rfind("::")] if "::" in nm else "(глобальные функции)"
            by_cls[c] += 1

tot = sum(by_mod.values()) + idle
print("всего сэмплов: %d, из них idle(Sleep/Wait): %d (%.1f%%)" % (tot, idle, 100.0*idle/tot))
print("\n=== по модулям (только исполняемый код) ===")
for m, c in by_mod.most_common(12):
    print("  %6d  %5.1f%%  %s" % (c, 100.0*c/tot, m))
print("\n===PhysX/драйвер/система суммарно ===")
physx = sum(v for k,v in by_mod.items() if k.lower().startswith("physx"))
print("  PhysX3_x64.dll: %.1f%%" % (100.0*physx/tot))
print("\n=== игровые подсистемы (классы, топ-25) ===")
for c, n in by_cls.most_common(25):
    print("  %5.1f%%  %s" % (100.0*n/tot, c))

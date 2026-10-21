import io, json, sqlite3, struct, collections, bisect, os
# топ функций из профиля ПОСЛЕ правок
b = r"C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi\Plugins\TickProf\prof_215945187.bin"
with open(b, "rb") as f:
    base, count = struct.unpack("<QQ", f.read(16))
    rips = struct.unpack("<%dQ" % count, f.read(8*count))
con = sqlite3.connect(r"C:\Dev\_research\v361.sqlite")
rows = con.execute("SELECT rva, name, size FROM fn WHERE tag=5 ORDER BY rva").fetchall()
con.close()
rvas = [r for r, n, s in rows]
info = [(n, s if s > 0 else 0x40) for r, n, s in rows]
cnt = collections.Counter()
for rip in rips:
    rva = rip - base
    i = bisect.bisect_right(rvas, rva) - 1
    if i >= 0 and rva < rvas[i] + info[i][1]:
        cnt[info[i][0]] += 1
idx = json.load(io.open("dump_index.json", encoding="utf-8"))
dumpnames = set(idx.keys())
print("топ-40 функций профиля и есть ли они в дампе ARK:\n")
tot = sum(cnt.values())
for n, c in cnt.most_common(40):
    short = n.split("::")[-1] if "::" in n else n
    hit = "ДА " if n in dumpnames else ("через " + next((x for x in dumpnames if x.endswith("::" + short) and len(x) < len(n) + 40), "нет"))
    print("  %5.2f%%  %-58s %s" % (100.0*c/tot, n[:58], hit[:60]))

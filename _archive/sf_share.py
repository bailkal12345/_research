import io, json, struct, collections, bisect, sqlite3
con = sqlite3.connect(r"C:\Dev\_research\v361.sqlite")
rows = con.execute("SELECT rva, name, size FROM fn WHERE tag=5 ORDER BY rva").fetchall()
con.close()
rvas=[r for r,n,s in rows]; info=[(n,s if s>0 else 0x40) for r,n,s in rows]
def look(rva):
    i=bisect.bisect_right(rvas,rva)-1
    if i>=0 and rva < rvas[i]+info[i][1]: return info[i][0]
    return None
for b in (r"C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi\Plugins\TickProf\prof_242291359.bin",
          r"C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi\Plugins\TickProf\prof_250759015.bin"):
    with open(b,"rb") as f:
        base,count=struct.unpack("<QQ", f.read(16)); rips=struct.unpack("<%dQ"%count, f.read(8*count))
    sf=0; inside=collections.Counter(); tot=0
    for rip in rips:
        rva=rip-base; nm=look(rva); tot+=1
        if nm=="FTickTaskManager::StartFrame": sf+=1
        inside[nm or "<внешний>"]+=1
    print("%s: %d сэмплов, внутри StartFrame %d (%.1f%%)" % (b.rsplit("\\",1)[-1], tot, sf, 100.0*sf/tot))
    print("   топ-12 функций всего:", ", ".join("%s %.1f%%"%(k[:34],100.0*v/tot) for k,v in inside.most_common(12)))
    print()

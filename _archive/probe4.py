import io
src = r"C:\Dev\ARK_SE_code_dump\game_aquatica.c"
want = [(2846820, 2846900, "ANPCZoneManager::UpdateZone"),
        (4135412, 4135500, "UVictoryCore::ServerOctreeOverlapActorsBitMask")]
with io.open(src, encoding="utf-8", errors="replace") as f:
    i = 0
    for ln in f:
        for a,b,tag in want:
            if a <= i < b:
                print("%s|%s" % (tag, ln.rstrip()[:150]))
        i += 1
        if i > 4135500:
            break

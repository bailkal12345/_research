import io
src = r"C:\Dev\ARK_SE_code_dump\game_aquatica.c"
needles = ["APrimalDinoCharacter::Tick", "APrimalCharacter::Tick", "ANPCZoneManager::Tick",
           "ServerOctreeOverlapActorsBitMask", "UClass::FindFunctionByName"]
hits = {n: [] for n in needles}
with io.open(src, encoding="utf-8", errors="replace") as f:
    for i, ln in enumerate(f):
        for n in needles:
            if n in ln and len(hits[n]) < 3:
                hits[n].append((i, ln.rstrip()[:150]))
for n in needles:
    print("==", n)
    for i, ln in hits[n]:
        print("   %d: %s" % (i, ln))

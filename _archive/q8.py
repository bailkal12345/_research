import sqlite3
con = sqlite3.connect(r"C:\Dev\_research\v361.sqlite")
for pat in ("UClass::FindFunctionByName%", "UVictoryCore::ServerOctreeOverlapActorsBitMask%",
            "AActor::TickActor%", "ANPCZoneManager::UpdateZone%", "FPostConstructInitializeProperties%",
            "UPrimitiveComponent::BeginComponentOverlap%", "APrimalDinoCharacter::Tick%"):
    rows = con.execute("SELECT name, rva, size FROM fn WHERE name LIKE ? LIMIT 3", (pat,)).fetchall()
    print("==", pat)
    for n,r,s in rows:
        print("   0x%08X %-58s %d" % (r, n[:58], s))
con.close()

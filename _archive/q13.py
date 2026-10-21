import sqlite3
con = sqlite3.connect(r"C:\Dev\_research\v361.sqlite")
for pat in ("UEngine::TickFPSChart%","FEngineStatGroup::Tick%","IncrementalPurgeGarbage%",
            "UBlackboardComponent::GetValueAsBool%","AAIController::GetFocalPoint%","UObject::ProcessEvent%"):
    rows = con.execute("SELECT name, rva, size FROM fn WHERE name LIKE ? LIMIT 2",(pat,)).fetchall()
    print("==", pat)
    for n,r,s in rows: print("   0x%08X %-46s %d" % (r,n[:46],s))
con.close()

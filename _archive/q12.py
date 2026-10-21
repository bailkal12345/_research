import sqlite3
con = sqlite3.connect(r"C:\Dev\_research\v361.sqlite")
for pat in ("UActorComponent::SetComponentTickEnabled%","UActorComponent::SetComponentTickEnabledAsync%",
            "AActor::SetActorTickEnabled%","FTickTaskManager::StartFrame%","FTickTaskLevel::StartFrame%",
            "FTickTaskSequencer::StartFrame%"):
    rows = con.execute("SELECT name, rva, size FROM fn WHERE name LIKE ? LIMIT 2",(pat,)).fetchall()
    print("==", pat)
    for n,r,s in rows: print("   0x%08X %-52s %d" % (r,n[:52],s))
con.close()

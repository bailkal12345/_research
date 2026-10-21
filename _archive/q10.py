import sqlite3
con = sqlite3.connect(r"C:\Dev\_research\v361.sqlite")
pats = ("IConsoleManager::GetConsoleVariable%", "IConsoleManager::Get%", "IConsoleManager::FindConsoleVariable%",
        "UNetDriver::NetServerMaxTickRate%", "UEngine::GetMaxTickRate%", "UWorld::GetNetDriver%",
        "UNetDriver::SetMaxNetTickRate%", "UNetDriver::TickDispatch%")
for pat in pats:
    rows = con.execute("SELECT name, rva, size FROM fn WHERE name LIKE ? LIMIT 3", (pat,)).fetchall()
    print("==", pat)
    for n,r,s in rows:
        print("   0x%08X %-52s %d" % (r, n[:52], s))
con.close()

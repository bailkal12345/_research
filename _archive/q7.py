import sqlite3
con = sqlite3.connect(r"C:\Dev\_research\v361.sqlite")
for pat in ("UEngine::Exec%", "UGameEngine::Exec%", "UWorld::Exec%", "IConsoleManager::%"):
    rows = con.execute("SELECT name, rva, size FROM fn WHERE name LIKE ? LIMIT 6", (pat,)).fetchall()
    print("==", pat)
    for n,r,s in rows: print("   0x%X %-50s %d" % (r, n[:50], s))
con.close()

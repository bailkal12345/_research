import sqlite3
con = sqlite3.connect(r"C:\Dev\_research\v361.sqlite")
for pat in ("%TickRate%","%RateLimit%","%GameNetworkManager%","%NetworkRate%","%ServerMaxTick%"):
    rows = con.execute("SELECT name, rva, size FROM fn WHERE name LIKE ? LIMIT 10",(pat,)).fetchall()
    print("==", pat, "->", len(rows))
    for n,r,s in rows: print("   0x%08X %-62s %d" % (r,n[:62],s))
con.close()

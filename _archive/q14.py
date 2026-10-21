import sqlite3
con = sqlite3.connect(r"C:\Dev\_research\v361.sqlite")
for pat in ("%GetMaxNetTickRate%","%FNetworkRateLimiter%","%RateLimiter%","%UNetDriver::TickFlush%","%UpdateTimeAndHandleMaxTickRate%"):
    rows = con.execute("SELECT name, rva, size FROM fn WHERE name LIKE ? LIMIT 6",(pat,)).fetchall()
    print("==", pat, len(rows))
    for n,r,s in rows: print("   0x%08X %-58s %d" % (r,n[:58],s))
con.close()

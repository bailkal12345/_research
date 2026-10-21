import sqlite3
c=sqlite3.connect(r"C:\Dev\_research\v361.sqlite"); cur=c.cursor()
for a in (0x3C632B0,0x1F432B0,0x1F432F0):
    print("=== around 0x%08X ==="%a)
    cur.execute("SELECT name,rva,size FROM fn WHERE rva BETWEEN ? AND ? ORDER BY rva",(a-0x30,a+0x60))
    for r in cur.fetchall(): print("  0x%08X %5d %s"%(r[1],r[2],r[0]))

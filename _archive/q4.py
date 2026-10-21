import sqlite3
con = sqlite3.connect(r"C:\Dev\_research\v361.sqlite")
rows = con.execute("SELECT name, rva, size FROM fn WHERE name LIKE '%AddUniqueImpl%' AND name LIKE '%OverlapInfo%'").fetchall()
for n,r,s in rows: print("0x%X  %-70s %d" % (r, n[:70], s))
print("---")
for n,r,s in con.execute("SELECT name, rva, size FROM fn WHERE name LIKE '%FOverlapResult%' OR name LIKE 'FOverlapInfo::%'").fetchall()[:12]:
    print("0x%X  %-70s %d" % (r, n[:70], s))
con.close()

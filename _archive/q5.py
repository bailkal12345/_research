import sqlite3
con = sqlite3.connect(r"C:\Dev\_research\v361.sqlite")
for pat in ("%FFoliageMeshInfo%FindId%", "FName::InitInternal_FindOrAddNameEntry%"):
    for n,r,s in con.execute("SELECT name, rva, size FROM fn WHERE name LIKE ? LIMIT 4", (pat,)):
        print("0x%X  %-80s %d" % (r, n[:80], s))
con.close()

import sqlite3
con = sqlite3.connect(r"C:\Dev\_research\v361.sqlite")
for pat in ("UObjectBaseUtility::IsA%", "UStruct::IsChildOf%", "UObject::ExecuteUbergraph%"):
    for n,r,s in con.execute("SELECT name, rva, size FROM fn WHERE name LIKE ? LIMIT 2",(pat,)):
        print("0x%08X %-45s %d" % (r, n, s))
con.close()

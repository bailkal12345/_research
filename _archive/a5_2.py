import sqlite3
c = sqlite3.connect(r"C:\Dev\_research\v361.sqlite")
cur = c.cursor()
cur.execute("SELECT name,rva,size FROM fn WHERE name LIKE \x27UObject::exec%\x27 ORDER BY rva")
rows = cur.fetchall()
print("TOTAL exec* =", len(rows))
tot=0
for n,r,s in rows:
    print("%08X %6d  %s" % (r,s,n))
    tot+=s
print("TOTAL BYTES =", tot)

import sqlite3
c = sqlite3.connect(r"C:\Dev\_research\v361.sqlite")
cur=c.cursor()
cur.execute("SELECT name,rva,size FROM fn WHERE rva>=? AND rva<? ORDER BY rva",(0x1FC35F0,0x1FC4000))
for r in cur.fetchall(): print("%08X %6d %s"%(r[1],r[2],r[0]))
print("=== how many UObjectexec*Registar ===")
cur.execute("SELECT count(*) FROM fn WHERE name LIKE \x27%exec%Registar%\x27 AND name LIKE \x27dynamic initializer%\x27")
print(cur.fetchone())

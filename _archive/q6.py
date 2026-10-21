import sqlite3
con = sqlite3.connect(r"C:\Dev\_research\v361.sqlite")
for n,r,s in con.execute("SELECT name, rva, size FROM fn WHERE name LIKE '%Canvas%Name%' AND name NOT LIKE '%Z_Construct%' LIMIT 10"):
    print("0x%X  %-60s %d" % (r, n[:60], s))
con.close()

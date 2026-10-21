import sqlite3
c = sqlite3.connect(r'C:\Dev\_research\v361.sqlite')
for p in ['%WorldSaveVersion%','%SaveVersion%','%IsSavingSaveGame%','%GSave%','%SaveGameFlag%','%CustomVersion%']:
    rows = c.execute("select name,rva,size,tag from sym where name like ? and size>=0 limit 25",(p,)).fetchall()
    print("=== "+p)
    for r in rows[:25]: print("  %08X t%d  %s"%(r[1],r[3],r[0][:110]))

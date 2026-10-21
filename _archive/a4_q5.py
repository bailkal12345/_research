import sqlite3, re
c = sqlite3.connect(r'C:\Dev\_research\v361.sqlite')
pats = ["%SaveInterval%", "%AutoSave%", "%autosav%", "%SaveWorld%", "%SAVEGAME%", "%SaveGameFlag%",
        "%IncrementalSave%", "%SaveData%", "%NoDialog%", "%saveworld%", "%SaveWorldInterval%",
        "%Hibernat%Function%", "%bIsSaving%"]
for p in pats:
    rows = c.execute("select name,rva,size,tag from sym where name like ? and size>0 order by rva limit 25",(p,)).fetchall()
    print("=== "+p+" (%d)"%len(c.execute("select 1 from sym where name like ?",(p,)).fetchall()))
    for r in rows:
        print("  %08X %5d t%d  %s"%(r[1],r[2],r[3],r[0][:110]))

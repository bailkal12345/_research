import sqlite3
c = sqlite3.connect(r'C:\Dev\_research\v361.sqlite')
pats = ["%PreSave%", "%PostSave%", "%SaveWorld%", "%::Serialize%", "%InventoryComponent%"]
for p in ["%PreSave%","%PostSave%","%PreSaveWorld%","%PostSaveWorld%"]:
    rows = c.execute("select name,rva,size from fn where name like ? and name not like '%dtor%' and name not like '%Z_Construct%' and name not like '%FDetermineBitMask%' order by name limit 40",(p,)).fetchall()
    print("=== "+p+" n=%d"%len(c.execute("select 1 from fn where name like ?",(p,)).fetchall()))
    for r in rows: print("  %08X %5d  %s"%(r[1],r[2],r[0]))
rows = c.execute("select name,rva,size from fn where name like '%UPrimalInventoryComponent::%' and name not like '%Z_Construct%' and name not like '%FDetermine%' and name not like '%dtor%' order by rva").fetchall()
print("=== UPrimalInventoryComponent members (%d)"%len(rows))
for r in rows:
    if 'Serialize' in r[0] or 'Save' in r[0] or 'PostLoad' in r[0] or 'Tick' in r[0] or 'Refresh' in r[0]:
        print("  %08X %5d  %s"%(r[1],r[2],r[0]))

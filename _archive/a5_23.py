import sqlite3
c=sqlite3.connect(r"C:\Dev\_research\v361.sqlite"); cur=c.cursor()
for nm in ["FName::GetNames","TStaticIndirectArrayThreadSafeRead<FNameEntry,4194304,16384>::GetNames","UObject::ProcessEvent","UFunction::Bind","FName::AppendString"]:
    cur.execute("SELECT DISTINCT name,rva,size FROM fn WHERE name=? OR name LIKE ?",(nm,"%"+nm+"%"))
    for n,r,s in cur.fetchall()[:6]: print("0x%08X %6d  %s"%(r,s,n))

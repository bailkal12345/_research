import sqlite3
c=sqlite3.connect(r"C:\Dev\_research\v361.sqlite"); cur=c.cursor()
for pat in ["FName::ToString","FName::To","FName::Get","NamePool","FNameEntry","FName::Append","UObjectBaseUtility::GetName","UObject::GetPathName","FString::Printf"]:
    cur.execute("SELECT name,rva,size FROM fn WHERE name LIKE ? ORDER BY rva LIMIT 14",(pat,))
    print("=== "+pat)
    for r in cur.fetchall(): print("  0x%08X %5d %s"%(r[1],r[2],r[0]))

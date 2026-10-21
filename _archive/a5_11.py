import sqlite3
c=sqlite3.connect(r"C:\Dev\_research\v361.sqlite"); cur=c.cursor()
cur.execute("SELECT name,rva,size,tag FROM sym WHERE rva BETWEEN ? AND ?",(0x491C6B0-0x40,0x491C6B0+0x40))
print("--- syms near GNatives 0x491C6B0 ---")
for r in cur.fetchall(): print("  0x%08X %5d %s"%(r[1],r[2],r[0]))
for pat in ["staticRegisterNatives","GetFunctionCallspace","GetReturnProperty","GetInterfaceAddress","::GetName","UObject::exec\b"]:
    cur.execute("SELECT name,rva,size FROM fn WHERE name LIKE ? ORDER BY rva LIMIT 15",("%"+pat.replace("\\b","")+"%",))
    print("=== "+pat)
    for r in cur.fetchall(): print("  0x%08X %5d %s"%(r[1],r[2],r[0]))

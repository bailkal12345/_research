import sqlite3,re
c=sqlite3.connect(r"C:\Dev\_research\v361.sqlite"); cur=c.cursor()
cur.execute("SELECT name,rva,size FROM fn WHERE name LIKE ? AND name LIKE ? ORDER BY rva",("%UObjectexec%","%BytecodeTemp%"))
rows=sorted(set(cur.fetchall()))
print("COUNT =",len(rows))
for n,r,s in rows:
    nm=re.search(r"UObjectexec(\w+)BytecodeTemp",n)
    print("0x%08X %4d %s"%(r,s,nm.group(1) if nm else n))

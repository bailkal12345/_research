import sqlite3,re
c=sqlite3.connect(r"C:\Dev\_research\v361.sqlite"); cur=c.cursor()
cur.execute("SELECT name,rva,size FROM fn WHERE name LIKE \x27dynamic initializer for \\x27UObjectexec%BytecodeTemp\\x27()\x27 ORDER BY rva")
rows=sorted(set(cur.fetchall()))
print("COUNT BytecodeTemp initializers =",len(rows))
for n,r,s in rows:
    nm=re.search(r"UObjectexec(\w+)BytecodeTemp",n).group(1)
    print("0x%08X %4d %s"%(r,s,nm))

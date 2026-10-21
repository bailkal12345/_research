import sqlite3
c=sqlite3.connect(r"C:\Dev\_research\v361.sqlite"); cur=c.cursor()
cur.execute("SELECT DISTINCT name,rva,size FROM fn WHERE name LIKE \x27UObject::exec%\x27 ORDER BY rva")
rows=cur.fetchall()
print("DISTINCT UObject::exec* =",len(rows))
# group by rva (aliases share rva)
byr={}
for n,r,s in rows: byr.setdefault(r,[]).append((n,s))
print("DISTINCT addresses =",len(byr))
tot=0
for r in sorted(byr):
    l=sorted(byr[r]); sz=max(x[1] for x in l); tot+=sz
    print("0x%08X %5d  %s"%(r,sz," | ".join("%s"%x[0] for x in l)))
print("TOTAL CODE BYTES(exec block) =",tot)

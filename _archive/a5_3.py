import sqlite3
c = sqlite3.connect(r"C:\Dev\_research\v361.sqlite")
cur = c.cursor()
cur.execute("SELECT count(*) FROM fn"); print("fn rows:", cur.fetchone())
cur.execute("SELECT count(*) FROM sym"); print("sym rows:", cur.fetchone())
cur.execute("PRAGMA table_info(fn)"); print("fn cols:", cur.fetchall())
cur.execute("PRAGMA table_info(sym)"); print("sym cols:", cur.fetchall())
cur.execute("SELECT name,rva,size FROM fn WHERE name LIKE \x27%exec%\x27 ORDER BY rva")
rows=sorted(set(cur.fetchall()))
print("UNIQUE %exec% =", len(rows))
seen=set()
for n,r,s in rows:
    k=(n,r)
    if k in seen: continue
    seen.add(k)
print("--- non UObject:: exec ---")
for n,r,s in sorted(set(rows)):
    if not n.startswith("UObject::exec"): print("%08X %6d %s"%(r,s,n))

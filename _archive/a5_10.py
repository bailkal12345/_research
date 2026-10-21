import sqlite3
c=sqlite3.connect(r"C:\Dev\_research\v361.sqlite"); cur=c.cursor()
for pat in ["GNatives","NativeFunc","ScriptNative","NativeExec"]:
    cur.execute("SELECT name,rva,size,tag FROM sym WHERE name LIKE ? LIMIT 30",("%"+pat+"%",))
    print("=== sym",pat)
    for r in cur.fetchall(): print("  ",r)
cur.execute("SELECT name FROM sqlite_master WHERE type=\x27table\x27")
for t in ["sym"]:
    cur.execute("PRAGMA table_info(%s)"%t); print(t,cur.fetchall())

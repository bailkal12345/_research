import sqlite3
c = sqlite3.connect(r"C:\Dev\_research\v361.sqlite")
cur = c.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type=\x27table\x27")
print("TABLES:", [r[0] for r in cur.fetchall()])
for pat in ["ProcessInternal","ProcessContextOpcode","UFunction::Invoke","CallFunction"]:
    cur.execute("SELECT name,rva,size,tag FROM fn WHERE name LIKE ? LIMIT 20", ("%"+pat+"%",))
    print("=== ", pat)
    for r in cur.fetchall(): print(r)

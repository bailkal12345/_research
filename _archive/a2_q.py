import sqlite3, sys
con = sqlite3.connect(r'C:\Dev\_research\v361.sqlite')
cur = con.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("TABLES:", cur.fetchall())

q = sys.argv[1] if len(sys.argv) > 1 else '%VictoryCore%'
cur.execute("SELECT name, rva, size, tag FROM fn WHERE name LIKE ? ORDER BY rva", (q,))
rows = cur.fetchall()
print("MATCHES:", len(rows))
for n, r, s, t in rows:
    print("0x%08X  sz=%-6d tag=%s  %s" % (r, s, t, n))
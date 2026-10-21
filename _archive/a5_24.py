import sqlite3,re
c=sqlite3.connect(r"C:\Dev\_research\v361.sqlite"); cur=c.cursor()
cur.execute("SELECT DISTINCT name FROM fn WHERE name LIKE \x27UObject::exec%\x27")
ex=sorted(set(r[0][len("UObject::exec"):] for r in cur.fetchall()))
cur.execute("SELECT DISTINCT name FROM fn WHERE name LIKE ? AND name LIKE ?",("%UObjectexec%","%BytecodeTemp%"))
reg=sorted(set(re.search(r"UObjectexec(\w+)BytecodeTemp",r[0]).group(1) for r in cur.fetchall()))
print("fn exec* names:",len(ex)," registered:",len(reg))
print("in fn but NOT registered:",[n for n in ex if n not in reg])
print("registered but not in fn:",[n for n in reg if n not in ex])

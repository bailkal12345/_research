import sqlite3
c=sqlite3.connect(r"C:\Dev\_research\v361.sqlite"); cur=c.cursor()
for pat in ["FFrame::FFrame","FFrame::~FFrame","UObject::ProcessEvent","FFrame::ReadVariableSize","UObject::SkipFunction","FFrame::"]:
    cur.execute("SELECT name,rva,size FROM fn WHERE name LIKE ? ORDER BY rva",(pat,))
    print("=== "+pat)
    for r in cur.fetchall()[:12]: print("  0x%08X %5d %s"%(r[1],r[2],r[0]))
print("=== syms at 0x1445C36B0 / 0x144A7C9A4 ===")
for a in (0x45C36B0,0x4A7C9A4):
    cur.execute("SELECT name,rva,size,tag FROM sym WHERE rva BETWEEN ? AND ?",(a-0x20,a+0x20))
    for r in cur.fetchall(): print("  0x%08X %5d %s"%(r[1],r[2],r[0]))

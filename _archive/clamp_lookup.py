import sqlite3
con = sqlite3.connect(r"C:\Dev\_research\v361.sqlite")
for pat in ("%GetMaxTickRate%", "%GameEngine::Tick%", "UGameEngine%Tick%", "%FEngineLoop::Tick%"):
    print("== ", pat)
    for n,r,s in con.execute("SELECT name,rva,size FROM fn WHERE name LIKE ? LIMIT 8",(pat,)):
        print("   0x%08X %-56s %d" % (r,n,s))
print()
print("== UNetDriver GetMaxTickRate / NetServerMaxTickRate:")
for pat in ("%UNetDriver::GetMaxTickRate%","%GetMaxTickRate%NetDriver%","%UNetDriver::TickDispatch%","%MaxNetTickRate%"):
    rows=con.execute("SELECT name,rva,size FROM fn WHERE name LIKE ? LIMIT 5",(pat,)).fetchall()
    if rows:
        print("  [%s]"%pat)
        for n,r,s in rows: print("   0x%08X %-52s %d"%(r,n,s))
con.close()

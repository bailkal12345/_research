import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(p, encoding="utf-8").read()
s = s.replace('\tcmds.AddRconCommand("TickProf.count",',
 '\tcmds.AddRconCommand("TickProf.fncache", [](RCONClientConnection* c, RCONPacket* p, UWorld* w) { CmdFnCache(c, p, w); });\n'
 '\tcmds.AddRconCommand("TickProf.overlapall", [](RCONClientConnection* c, RCONPacket* p, UWorld* w) { CmdOverlapAll(c, p, w); });\n'
 '\tcmds.AddRconCommand("TickProf.count",')
s = s.replace('"TickProf.overlapsizes", "TickProf.overlaptrim"})',
              '"TickProf.overlapsizes", "TickProf.overlaptrim", "TickProf.fncache", "TickProf.overlapall"})')
io.open(p, "w", encoding="utf-8").write(s)
print("ok")

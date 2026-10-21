import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(p, encoding="utf-8").read()
s = s.replace('\tcmds.AddRconCommand("TickProf.count",',
 '\tcmds.AddRconCommand("TickProf.iscache", [](RCONClientConnection* c, RCONPacket* p, UWorld* w) { CmdIsCache(c, p, w); });\n'
 '\tcmds.AddRconCommand("TickProf.count",')
s = s.replace('"TickProf.fncache", "TickProf.overlapall"})',
              '"TickProf.fncache", "TickProf.overlapall", "TickProf.iscache"})')
io.open(p, "w", encoding="utf-8").write(s)
print("ok")

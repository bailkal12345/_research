import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(p, encoding="utf-8").read()
s = s.replace('\tcmds.AddRconCommand("TickProf.cull",',
 '\tcmds.AddRconCommand("TickProf.nochart", [](RCONClientConnection* c, RCONPacket* p, UWorld* w) { CmdNoChart(c, p, w); });\n'
 '\tcmds.AddRconCommand("TickProf.cull",')
s = s.replace('"TickProf.tickclasses",\n\t\t\t "TickProf.tickoff"})',
              '"TickProf.tickclasses",\n\t\t\t "TickProf.tickoff", "TickProf.nochart"})')
io.open(p, "w", encoding="utf-8").write(s)
print("ok")

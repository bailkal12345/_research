import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(p, encoding="utf-8").read()
s = s.replace('#include <algorithm>', '#include <algorithm>\n#include <functional>')
s = s.replace('\tcmds.AddRconCommand("TickProf.count",',
              '\tcmds.AddRconCommand("TickProf.overlapsizes", [](RCONClientConnection* c, RCONPacket* p, UWorld* w) { CmdOverlapSizes(c, p, w); });\n'
              '\tcmds.AddRconCommand("TickProf.overlaptrim", [](RCONClientConnection* c, RCONPacket* p, UWorld* w) { CmdOverlapTrim(c, p, w); });\n'
              '\tcmds.AddRconCommand("TickProf.count",')
s = s.replace('"TickProf.cachename", "TickProf.spawn", "TickProf.cleardinos", "TickProf.count"})',
              '"TickProf.cachename", "TickProf.spawn", "TickProf.cleardinos", "TickProf.count",\n\t\t\t "TickProf.overlapsizes", "TickProf.overlaptrim"})')
io.open(p, "w", encoding="utf-8").write(s)
print("ok")

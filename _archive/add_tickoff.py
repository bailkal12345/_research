import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(p, encoding="utf-8").read()
s = s.replace("#include <functional>", "#include <functional>\n#include <unordered_map>")
# общий обход компонентов рядом с обходом primitive-компонентов
anchor = "\t// ------------------------------------------------- размеры OverlappingComponents"
helper = '''\t// Обход всех компонентов: один вызов движка вместо ручного обхода TSet.
\tvoid ForEachComponent(const std::function<void(UActorComponent*)>& fn)
\t{
\t\tUClass* cls = NativeCall<UClass*>(nullptr, "UActorComponent.StaticClass");
\t\tif (!cls)
\t\t\treturn;
\t\tTArray<UObject*> comps;
\t\tGlobals::GetObjectsOfClass(cls, &comps, true, EObjectFlags::RF_Transient);
\t\tfor (int32_t i = 0; i < comps.Num(); ++i)
\t\t{
\t\t\tif (comps[i])
\t\t\t\tfn(static_cast<UActorComponent*>(comps[i]));
\t\t}
\t}

'''
s = s.replace(anchor, helper + anchor)
s = s.replace('\tcmds.AddRconCommand("TickProf.cull",',
 '\tcmds.AddRconCommand("TickProf.tickclasses", [](RCONClientConnection* c, RCONPacket* p, UWorld* w) { CmdTickClasses(c, p, w); });\n'
 '\tcmds.AddRconCommand("TickProf.tickoff", [](RCONClientConnection* c, RCONPacket* p, UWorld* w) { CmdTickOff(c, p, w); });\n'
 '\tcmds.AddRconCommand("TickProf.cull",')
s = s.replace('"TickProf.maxfps", "TickProf.cull", "TickProf.cullstat"})',
              '"TickProf.maxfps", "TickProf.cull", "TickProf.cullstat", "TickProf.tickclasses",\n\t\t\t "TickProf.tickoff"})')
io.open(p, "w", encoding="utf-8").write(s)
print("ok")

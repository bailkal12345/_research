import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(p, encoding="utf-8").read()
# 'near' — макрос Windows (windef.h), переименуем
s = s.replace("TArray<AActor*> near =\n\t\t\tArkApi::GetApiUtils().GetAllActorsInRange(center, 200000.0f, EServerOctreeGroup::TARGETABLEACTORS);",
              "TArray<AActor*> nearActors =\n\t\t\tArkApi::GetApiUtils().GetAllActorsInRange(center, 200000.0f, EServerOctreeGroup::TARGETABLEACTORS);")
s = s.replace("near.Num()", "nearActors.Num()")
s = s.replace("g_phases[P_NetDriverTickDispatch]", "g_phases[P_NetTickDispatch]")
io.open(p, "w", encoding="utf-8").write(s)
print("fixed")

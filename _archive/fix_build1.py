import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(p, encoding="utf-8").read()

# прототипы для функций, объявленных ниже точки использования
s = s.replace("	constexpr const char* PLUGIN_NAME = \"TickProf\";",
"""	constexpr const char* PLUGIN_NAME = "TickProf";

	void VerifyConcurrent();
	void OnTickPerf(float);""")

s = s.replace("TArray<ULevel*>& levels = world->LevelsField();", "TArray<ULevel*> levels = world->LevelsField();")
io.open(p, "w", encoding="utf-8").write(s)
print("ok")

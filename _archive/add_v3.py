import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(p, encoding="utf-8").read()
add = '''
	// --------------------------------------------- overlaptrim v3 с белой меткой
	// v1/v2 снимали bGenerateOverlapEvents со всех перегруженных компонентов подряд,
	// включая те, чьи overlap-события нужны игровой логике: ABaseBoxTrigger
	// (BPOnTriggerBeginOverlap), APrimalStructureTurret, ловушки оглушения,
	// APrimalProjectileGrapplingHook. v3 исключает классы из файла
	// tickprof_overlap_keep.txt (подстроки полного имени класса, одна в строке).
	// По умолчанию применяется встроенный список форм-компонентов.
	const char* DEFAULT_KEEP[] = {
		"ShapeComponent", "SphereComponent", "BoxComponent", "CapsuleComponent",
		"Trigger", "Turret", "GrapplingHook",
	};

	std::vector<std::string> LoadKeepList()
	{
		std::vector<std::string> out;
		FILE* f = nullptr;
		const std::string path = PluginDir() + "\\\\tickprof_overlap_keep.txt";
		if (fopen_s(&f, path.c_str(), "rb") == 0 && f)
		{
			char buf[512];
			while (fgets(buf, sizeof(buf), f))
			{
				std::string t(buf);
				while (!t.empty() && (t.back() == '\\n' || t.back() == '\\r' || t.back() == ' '))
					t.pop_back();
				if (!t.empty() && t[0] != '#')
					out.push_back(t);
			}
			fclose(f);
		}
		if (out.empty())
		{
			for (const char* k : DEFAULT_KEEP)
				out.emplace_back(k);
		}
		return out;
	}

	void CmdOverlapTrim3(RCONClientConnection*, RCONPacket* packet, UWorld*)
	{
		const int32_t threshold = ArgInt(packet, 2);
		const std::vector<std::string> keep = LoadKeepList();
		int32_t touched = 0, skipped = 0;
		int64_t freed = 0;
		ForEachPrimitiveComponent([&](UPrimitiveComponent* c) {
			RawArray arr = *Arr(c, PRIM_OVERLAPPING);
			if (arr.num < threshold)
				return;
			const std::string name = ClassName(c);
			for (const auto& k : keep)
			{
				if (name.find(k) != std::string::npos)
				{
					++skipped;
					return;
				}
			}
			freed += arr.num;
			arr.data = nullptr;
			arr.num = 0;
			arr.max = 0;
			auto* flags = reinterpret_cast<uint32_t*>(reinterpret_cast<char*>(c) + PRIM_FLAGS);
			*flags &= ~PRIM_GENERATE_OVERLAP;
			++touched;
		});
		LogLine(S("overlaptrim3: порог={} правил белой метки={} отключено={} "
			"сохранено по метке={} освобождено записей={}", threshold, keep.size(), touched,
			skipped, freed));
	}

	// ------------------------------------------------- census overlap-событий'''
s = s.replace("	// ------------------------------------------------- census overlap-событий", add, 1)
s = s.replace('\tcmds.AddRconCommand("TickProf.overlaptrim",',
 '\tcmds.AddRconCommand("TickProf.overlaptrim3", [](RCONClientConnection* c, RCONPacket* p, UWorld* w) { CmdOverlapTrim3(c, p, w); });\n'
 '\tcmds.AddRconCommand("TickProf.overlaptrim",')
s = s.replace('"TickProf.overlapsizes", "TickProf.overlaptrim",',
              '"TickProf.overlapsizes", "TickProf.overlaptrim", "TickProf.overlaptrim3",')
io.open(p, "w", encoding="utf-8").write(s)
print("overlaptrim3 добавлен")

import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(p, encoding="utf-8").read()

s = s.replace('#include <API/ARK/Ark.h>', '#include <API/ARK/Ark.h>\n#include <Psapi.h>')

s = s.replace('''	void WriteResults()
	{''',
'''	// Карта модулей пишется вместе с профилем: без неё офлайн-символизация
	// не знает, куда отнести адреса вне образа игры (системные DLL переезжают
	// при каждом старте из-за ASLR).
	void WriteModuleMap(const std::string& path)
	{
		HMODULE mods[1024];
		DWORD needed = 0;
		if (!EnumProcessModules(GetCurrentProcess(), mods, sizeof(mods), &needed))
			return;
		const DWORD count = needed / sizeof(HMODULE);
		FILE* f = nullptr;
		if (fopen_s(&f, path.c_str(), "wb") != 0 || !f)
			return;
		fprintf(f, "base\\tsize\\tname\\n");
		for (DWORD i = 0; i < count; ++i)
		{
			char name[MAX_PATH] = {};
			GetModuleFileNameA(mods[i], name, MAX_PATH);
			MODULEINFO info{};
			GetModuleInformation(GetCurrentProcess(), mods[i], &info, sizeof(info));
			fprintf(f, "0x%llX\\t0x%X\\t%s\\n", static_cast<unsigned long long>(
				reinterpret_cast<uintptr_t>(info.lpBaseOfDll)), info.SizeOfImage, name);
		}
		fclose(f);
	}

	void WriteResults()
	{''')

s = s.replace('''			LogLine(S("wrote {}", csv_path));
		}
	}''',
'''			LogLine(S("wrote {}", csv_path));
		}

		char mname[128];
		snprintf(mname, sizeof(mname), "prof_%llu.modules.txt",
			static_cast<unsigned long long>(t));
		WriteModuleMap(PluginDir() + "\\\\" + mname);
	}''')

io.open(p, "w", encoding="utf-8").write(s)
print("patched plugin")

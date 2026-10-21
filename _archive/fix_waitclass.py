import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(p, encoding="utf-8").read()

# карта модулей с именами
s = s.replace('''	struct ModuleRange
	{
		uint64_t start;
		uint64_t end;
	};''','''	struct ModuleRange
	{
		uint64_t start;
		uint64_t end;
		bool is_sys;   // системные DLL: их заглушки означают ожидание
	};''')
s = s.replace('''			MODULEINFO info{};
			if (GetModuleInformation(GetCurrentProcess(), mods[i], &info, sizeof(info)))
			{
				g_mod_ranges.push_back({reinterpret_cast<uint64_t>(info.lpBaseOfDll),
					reinterpret_cast<uint64_t>(info.lpBaseOfDll) + info.SizeOfImage});
			}''','''			MODULEINFO info{};
			char name[MAX_PATH] = {};
			GetModuleFileNameA(mods[i], name, MAX_PATH);
			std::string base_name = name;
			const size_t slash = base_name.find_last_of("\\\\/");
			if (slash != std::string::npos)
				base_name = base_name.substr(slash + 1);
			std::string lower;
			for (char ch : base_name)
				lower.push_back(static_cast<char>(tolower(static_cast<unsigned char>(ch))));
			// в этих DLL живут заглушки системных вызовов: попадание RIP сюда
			// означает блокировку, а не работу движка
			const bool is_sys = (lower == "ntdll.dll" || lower == "win32u.dll" ||
				lower == "kernel32.dll" || lower == "kernelbase.dll" ||
				lower == "user32.dll" || lower == "gdi32.dll");
			if (GetModuleInformation(GetCurrentProcess(), mods[i], &info, sizeof(info)))
			{
				g_mod_ranges.push_back({reinterpret_cast<uint64_t>(info.lpBaseOfDll),
					reinterpret_cast<uint64_t>(info.lpBaseOfDll) + info.SizeOfImage, is_sys});
			}''')

# классификация: вне модулей ИЛИ внутри системной DLL
s = s.replace('''	bool RipInUserModule(uint64_t rip)
	{
		for (const auto& m : g_mod_ranges)
		{
			if (rip >= m.start && rip < m.end)
				return true;
		}
		return false;
	}''','''	// Возвращает true, если RIP означает блокировку: либо вне пользовательских
	// модулей (ядро), либо внутри системной DLL, где лежат заглушки вызовов.
	bool RipIsBlocked(uint64_t rip)
	{
		for (const auto& m : g_mod_ranges)
		{
			if (rip >= m.start && rip < m.end)
				return m.is_sys;
		}
		return true;
	}''')
s = s.replace("				if (!RipInUserModule(rip) && g_wait_stacks)",
              "				if (RipIsBlocked(rip) && g_wait_stacks)")
s = s.replace("#include <functional>", "#include <functional>\n#include <cctype>")
io.open(p, "w", encoding="utf-8").write(s)
print("ok")

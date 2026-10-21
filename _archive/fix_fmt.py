import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(p, encoding="utf-8").read()

old = """		std::string out;
		size_t ai = 0;
		for (const char* p = fmt; *p; ++p)
		{
			if (p[0] == '{' && p[1] == '}')
			{
				out += ai < parts.size() ? parts[ai] : std::string("{}");
				++ai;
				++p;
			}
			else
			{
				out.push_back(*p);
			}
		}
		return out;"""

new = """		std::string out;
		size_t ai = 0;
		for (const char* p = fmt; *p; ++p)
		{
			if (p[0] == '{' && p[1] == ':')
			{
				// спецификация вида {:X} / {:02X} — печатаем аргумент в hex
				const char* spec = p + 2;
				std::string sp;
				while (*spec && *spec != '}')
				{
					sp.push_back(*spec);
					++spec;
				}
				char buf[64];
				unsigned long long raw = 0;
				if (ai < parts.size())
				{
					sscanf(parts[ai].c_str(), "%llu", &raw);
					if (parts[ai].size() > 2 && parts[ai][0] == '0' && (parts[ai][1] == 'x' || parts[ai][1] == 'X'))
						sscanf(parts[ai].c_str() + 2, "%llx", &raw);
				}
				const bool zero_pad = sp.find('0') != std::string::npos;
				const int width = zero_pad ? static_cast<int>(sp.find('0') + 2) : 0;
				snprintf(buf, sizeof(buf), zero_pad ? "0%llX" : "%llX", raw);
				out += buf;
				(void)width;
				++ai;
				while (*spec)
					++spec;
				if (*spec == '}')
					++spec;
				p = spec - 1;
			}
			else if (p[0] == '{' && p[1] == '}')
			{
				out += ai < parts.size() ? parts[ai] : std::string("{}");
				++ai;
				++p;
			}
			else
			{
				out.push_back(*p);
			}
		}
		return out;"""

assert old in s
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8").write(s)
print("ok")

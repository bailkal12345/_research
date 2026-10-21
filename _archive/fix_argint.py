import io

P = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(P, encoding="utf-8", newline="").read().replace("\r\n", "\n")

# Настоящая семантика ArgInt(packet, def): взять ПОСЛЕДНИЙ токен команды,
# а N - это значение по умолчанию. Мои вызовы ArgInt(packet, 2) трактовали 2
# как номер аргумента, из-за чего порог всегда становился 2 по умолчанию,
# а лишние аргументы (например "20 120 0") игнорировались.
HELPERS = """	// Правильный разбор аргументов: N-й аргумент команды (1 = первый после
	// имени команды). Прежний ArgInt(packet, def) брал ПОСЛЕДНИЙ токен, из-за
	// чего "TickProf.overlaptrim 5" давал 2, а "selftest 20 120 0" - 0.
	std::vector<std::string> ArgTokens(RCONPacket* packet)
	{
		std::vector<std::string> out;
		if (!packet)
			return out;
		const std::string body = packet->Body.ToString();
		std::string cur;
		for (char c : body)
		{
			if (c == ' ')
			{
				if (!cur.empty())
					out.push_back(cur);
				cur.clear();
			}
			else
				cur.push_back(c);
		}
		if (!cur.empty())
			out.push_back(cur);
		return out;
	}

	int32_t ArgN(RCONPacket* packet, int idx, int32_t def)
	{
		const std::vector<std::string> t = ArgTokens(packet);
		// t[0] - имя команды; далее аргументы
		if (static_cast<size_t>(idx) + 1 >= t.size())
			return def;
		return atoi(t[idx + 1].c_str());
	}

	int32_t ArgLast(RCONPacket* packet, int32_t def)
	{
		const std::vector<std::string> t = ArgTokens(packet);
		if (t.size() < 2)
			return def;
		return atoi(t.back().c_str());
	}

	int ArgIntDef(RCONPacket* p, int idx, int def)
	{
		return ArgN(p, idx, def);
	}
"""
OLD_HELPER = """	// аргумент RCON с запасным значением
	int ArgIntDef(RCONPacket* p, int idx, int def)
	{
		const int32_t v = ArgInt(p, 20 + idx);
		return v > 0 ? v : def;
	}
"""
assert OLD_HELPER in s
s = s.replace(OLD_HELPER, HELPERS, 1)

# CmdOverlapTrim: порог = первый аргумент
s = s.replace("\t\tDoOverlapTrim(ArgInt(packet, 2));", "\t\tDoOverlapTrim(ArgN(packet, 0, 2));", 1)
# CmdOverlapAll: 1 = выключить генерацию
s = s.replace("\t\tDoOverlapAll(ArgInt(packet, 0) != 0);", "\t\tDoOverlapAll(ArgN(packet, 0, 0) != 0);", 1)
# selftest: бюджет/окно/профиль
s = s.replace("\t\tg_st_budget_min = ArgIntDef(packet, 0, 45);", "\t\tg_st_budget_min = ArgN(packet, 0, 45);", 1)
s = s.replace("\t\tg_st_win_sec = ArgIntDef(packet, 1, 240);", "\t\tg_st_win_sec = ArgN(packet, 1, 240);", 1)
s = s.replace("\t\tg_st_profile = ArgIntDef(packet, 2, 1) != 0;", "\t\tg_st_profile = ArgN(packet, 2, 1) != 0;", 1)

io.open(P, "w", encoding="utf-8", newline="\r\n").write(s)
print("ArgN/ArgLast добавлены; пороги и параметры selftest теперь разбираются по позиции")
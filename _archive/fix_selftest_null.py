import io

P = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(P, encoding="utf-8", newline="").read().replace("\r\n", "\n")

# 1) безопасные внутренние функции: тело логики выносится из RCON-обработчиков,
#    чтобы selftest не звал их с nullptr-пакетом (ArgInt(nullptr) = разыменование).
DECL = ("\t// внутренние функции без обращения к RCONPacket: их зовёт selftest\n"
        "\tint32_t DoOverlapTrim(int32_t threshold);\n"
        "\tint32_t DoOverlapAll(bool off);\n"
        "\tvoid DoOverlapsCensus();\n\n")
s = s.replace("\tvoid CmdOverlapAll(RCONClientConnection*, RCONPacket*, UWorld*);\n"
              "\tvoid CmdOverlapTrim(RCONClientConnection*, RCONPacket*, UWorld*);\n"
              "\tvoid CmdOverlaps(RCONClientConnection*, RCONPacket*, UWorld*);\n",
              DECL, 1)

# CmdOverlapAll -> тело в DoOverlapAll
OLD_ALL = """	void CmdOverlapAll(RCONClientConnection*, RCONPacket* packet, UWorld*)
	{
		const bool off = ArgInt(packet, 0) != 0; // 1 = выключить генерацию
		int32_t touched = 0;"""
NEW_ALL = """	int32_t DoOverlapAll(bool off)
	{
		int32_t touched = 0;"""
assert OLD_ALL in s
s = s.replace(OLD_ALL, NEW_ALL, 1)

OLD_ALL_END = """		LogLine(S("overlapall: bGenerateOverlapEvents {} у {} компонентов",
			off ? "снят" : "возвращён", touched));
	}"""
NEW_ALL_END = """		LogLine(S("overlapall: bGenerateOverlapEvents {} у {} компонентов",
			off ? "снят" : "возвращён", touched));
		return touched;
	}

	void CmdOverlapAll(RCONClientConnection*, RCONPacket* packet, UWorld*)
	{
		DoOverlapAll(ArgInt(packet, 0) != 0);
	}"""
assert OLD_ALL_END in s
s = s.replace(OLD_ALL_END, NEW_ALL_END, 1)

# CmdOverlapTrim -> тело в DoOverlapTrim
OLD_TRIM = """	void CmdOverlapTrim(RCONClientConnection*, RCONPacket* packet, UWorld*)
	{"""
NEW_TRIM = """	void CmdOverlapTrim(RCONClientConnection*, RCONPacket* packet, UWorld*)
	{
		DoOverlapTrim(ArgInt(packet, 2));
	}

	int32_t DoOverlapTrim(int32_t threshold)
	{"""
assert OLD_TRIM in s
s = s.replace(OLD_TRIM, NEW_TRIM, 1)

# CmdOverlaps -> переименовать тело в DoOverlapsCensus + обёртка
OLD_OV = """	void CmdOverlaps(RCONClientConnection*, RCONPacket* packet, UWorld*)
	{"""
NEW_OV = """	void CmdOverlaps(RCONClientConnection*, RCONPacket* packet, UWorld*)
	{
		DoOverlapsCensus();
	}

	void DoOverlapsCensus()
	{"""
assert OLD_OV in s
s = s.replace(OLD_OV, NEW_OV, 1)

# 2) selftest зовёт безопасные функции
s = s.replace("CmdOverlapAll(nullptr, nullptr, nullptr);", "DoOverlapAll(false);")
s = s.replace("CmdOverlapTrim(nullptr, nullptr, nullptr);", "DoOverlapTrim(2);")
s = s.replace("CmdOverlaps(nullptr, nullptr, nullptr);", "DoOverlapsCensus();")

io.open(P, "w", encoding="utf-8", newline="\r\n").write(s)
print("selftest переведён на безопасные внутренние функции (nullptr-пакет убран)")
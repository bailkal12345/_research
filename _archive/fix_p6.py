import io

P = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(P, encoding="utf-8", newline="").read().replace("\r\n", "\n")

# 1) atomic<double> не конвертируется неявно
s = s.replace("g_st_vals.push_back(g_win_ms_tick);",
              "g_st_vals.push_back(g_win_ms_tick.load());")
s = s.replace('S("selftest: опорное мс/тик = {}", g_win_ms_tick)',
              'S("selftest: опорное мс/тик = {}", g_win_ms_tick.load())')
s = s.replace('S("selftest: рука A мс/тик = {}", g_win_ms_tick)',
              'S("selftest: рука A мс/тик = {}", g_win_ms_tick.load())')
s = s.replace('S("selftest: рука B мс/тик = {}", g_win_ms_tick)',
              'S("selftest: рука B мс/тик = {}", g_win_ms_tick.load())')

# 2) ArgInt принимает 2 аргумента -> свой помощник со значением по умолчанию
HELP = ("\t// аргумент RCON с запасным значением\n"
        "\tint ArgIntDef(RCONPacket* p, int idx, int def)\n"
        "\t{\n"
        "\t\tconst int32_t v = ArgInt(p, 20 + idx);\n"
        "\t\treturn v > 0 ? v : def;\n"
        "\t}\n\n")
ANCHOR = "\t// =========================================================== мониторинг v2"
assert ANCHOR in s
if "ArgIntDef" not in s:
    s = s.replace(ANCHOR, HELP + ANCHOR, 1)

s = s.replace("g_st_budget_min = ArgInt(packet, 20, 45);", "g_st_budget_min = ArgIntDef(packet, 0, 45);")
s = s.replace("g_st_win_sec = ArgInt(packet, 21, 240);", "g_st_win_sec = ArgIntDef(packet, 1, 240);")
s = s.replace("g_st_profile = ArgInt(packet, 22, 1) != 0;", "g_st_profile = ArgIntDef(packet, 2, 1) != 0;")

io.open(P, "w", encoding="utf-8", newline="\r\n").write(s)
print("исправлено: atomic<double> и ArgIntDef")
import io
p = r"C:\Dev\_research\fix_p4.py"
s = io.open(p, encoding="utf-8").read()
add = '''
s = s.replace("g_st_vals.push_back(g_win_ms_tick);", "g_st_vals.push_back(g_win_ms_tick.load());")
s = s.replace('g_win_ms_tick));', 'g_win_ms_tick.load()));')
s = s.replace("g_st_budget_min = ArgInt(packet, 20, 45);", "g_st_budget_min = ArgIntDef(packet, 0, 45);")
s = s.replace("g_st_win_sec = ArgInt(packet, 21, 240);", "g_st_win_sec = ArgIntDef(packet, 1, 240);")
s = s.replace("g_st_profile = ArgInt(packet, 22, 1) != 0;", "g_st_profile = ArgIntDef(packet, 2, 1) != 0;")
HELP = "int ArgIntDef(RCONPacket* p, int idx, int def)\\n\\t{\\n\\t\\tconst int32_t v = ArgInt(p, 20 + idx);\\n\\t\\treturn v > 0 ? v : def;\\n\\t}\\n\\n"
s = s.replace('START = ', 'HELP = ' + repr(HELP) + '\nSTART = ', 1)
s = s.replace("s = s.replace(START, FWD + START, 1)", "s = s.replace(START, FWD + HELP + START, 1)")
io.open(p, "w", encoding="utf-8").write(s)
print("fix_p4 обновлён")

import io

P = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(P, encoding="utf-8", newline="").read().replace("\r\n", "\n")

FWD = ("\t// прямые вызовы нужны selftest'у, определения ниже по файлу\n"
       "\tvoid CmdOverlapAll(RCONClientConnection*, RCONPacket*, UWorld*);\n"
       "\tvoid CmdOverlapTrim(RCONClientConnection*, RCONPacket*, UWorld*);\n"
       "\tvoid CmdOverlaps(RCONClientConnection*, RCONPacket*, UWorld*);\n\n")

START = "\t// =========================================================== мониторинг v2"
assert START in s
s = s.replace(START, FWD + START, 1)

# g_win_ms_tick объявляем в начале блока, а не в конце
DECL = "\tstd::atomic<double> g_win_ms_tick{0.0};\n\n"
assert DECL in s, "объявление g_win_ms_tick не найдено"
s = s.replace(DECL, "", 1)
s = s.replace(START, START + "\n" + DECL, 1)

# вызовы с nullptr -> nullptr, nullptr
s = s.replace("CmdOverlapAll(nullptr, nullptr, 0);", "CmdOverlapAll(nullptr, nullptr, nullptr);")
s = s.replace("CmdOverlapTrim(nullptr, nullptr, 2);", "CmdOverlapTrim(nullptr, nullptr, nullptr);")
s = s.replace("CmdOverlaps(nullptr, nullptr, 0);", "CmdOverlaps(nullptr, nullptr, nullptr);")

io.open(P, "w", encoding="utf-8", newline="\r\n").write(s)
print("форвард-объявления и порядок объявлений исправлены")
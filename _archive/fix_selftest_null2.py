import io

P = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(P, encoding="utf-8", newline="").read().replace("\r\n", "\n")

# CmdOverlaps читал окно из пакета — в перенесённой функции пакета нет.
s = s.replace("\tvoid DoOverlapsCensus()\n\t{\n\t\tconst int32_t seconds = ArgInt(packet, 20);\n",
              "\tvoid DoOverlapsCensus(int32_t seconds)\n\t{\n", 1)

# DoOverlapTrim объявляет threshold, затем читает его из пакета — дубль.
s = s.replace("\tint32_t DoOverlapTrim(int32_t threshold)\n\t{\n\t\tconst int32_t threshold = ArgInt(packet, 32);\n",
              "\tint32_t DoOverlapTrim(int32_t threshold)\n\t{\n", 1)

# обёртки передают аргумент
s = s.replace("\tvoid CmdOverlaps(RCONClientConnection*, RCONPacket* packet, UWorld*)\n\t{\n\t\tDoOverlapsCensus();\n\t}",
              "\tvoid CmdOverlaps(RCONClientConnection*, RCONPacket* packet, UWorld*)\n\t{\n\t\tDoOverlapsCensus(ArgInt(packet, 20));\n\t}", 1)

s = s.replace("\tvoid DoOverlapsCensus();\n", "\tvoid DoOverlapsCensus(int32_t seconds);\n", 1)
s = s.replace("DoOverlapsCensus();", "DoOverlapsCensus(30);")

io.open(P, "w", encoding="utf-8", newline="\r\n").write(s)
print("аргументы перенесены в обёртки, тела чистые")
import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(p, encoding="utf-8").read()
# убрать преждевременно вставленную функцию
start = s.index("\tvoid CmdCacheStat(RCONClientConnection*, RCONPacket*, UWorld*)")
end = s.index("\tvoid CmdFnCache(RCONClientConnection*, RCONPacket* packet, UWorld*)")
s = s[:start] + s[end:]
# вставить в конец пространства имён
anchor = "\tvoid OnTickPerf"
blk = '''\tvoid CmdCacheStat(RCONClientConnection*, RCONPacket*, UWorld*)
\t{
\t\tconst uint64_t fh = g_fn_hit.load(), fm = g_fn_miss.load();
\t\tconst uint64_t ih = g_is_hit.load(), im = g_is_miss.load();
\t\tconst double ft = (fh + fm) ? 100.0 * fh / (fh + fm) : 0.0;
\t\tconst double it = (ih + im) ? 100.0 * ih / (ih + im) : 0.0;
\t\tLogLine(S("cachestat: fncache попаданий={} промахов={} ({:.1f}%)", fh, fm, ft));
\t\tLogLine(S("cachestat: iscache попаданий={} промахов={} ({:.1f}%)", ih, im, it));
\t}

'''
i = s.rindex(anchor)
s = s[:i] + blk + s[i:]
s = s.replace("CmdCacheStat();", "CmdCacheStat(nullptr, nullptr, nullptr);")
io.open(p, "w", encoding="utf-8").write(s)
print("ok")

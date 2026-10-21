import io, re

P = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(P, encoding="utf-8", newline="").read().replace("\r\n", "\n")

NAMES = [
    "g_save_state", "g_save_last_change", "g_save_count", "g_save_ms_total",
    "g_win_valid", "g_win_frames_during_save", "g_win_ms_tick",
    "g_win_cpu0", "g_mon_cpu0", "g_mon_left", "g_mon_frames", "g_mon_cpu",
]

# вырезаем все объявления этих переменных откуда бы они ни стояли
for n in NAMES:
    s = re.sub(r"^\tstd::atomic<[^>]*> " + n + r"\{[^}]*\};\n", "", s, flags=re.M)
    s = re.sub(r"^\tstd::atomic<[^>]*> " + n + r";\n", "", s, flags=re.M)

DECLS = """\t// ---- общие переменные блока (объявлены здесь, чтобы порядок не зависел
\t// от того, где оказались функции) ----
\tstd::atomic<int> g_save_state{0};
\tstd::atomic<uint64_t> g_save_last_change{0};
\tstd::atomic<int> g_save_count{0};
\tstd::atomic<uint64_t> g_save_ms_total{0};
\tstd::atomic<int> g_win_valid{1};
\tstd::atomic<uint64_t> g_win_frames_during_save{0};
\tstd::atomic<double> g_win_ms_tick{0.0};
\tstd::atomic<uint64_t> g_win_cpu0{0};
\tstd::atomic<uint64_t> g_mon_cpu0{0};
\tstd::atomic<int> g_mon_left{0};
\tstd::atomic<uint64_t> g_mon_frames{0};
\tstd::atomic<uint64_t> g_mon_cpu{0};
\tuint64_t g_mon_mark_ms = 0;
\tuint64_t g_ark_poll_ms = 0;
\tstd::string g_ark_dir;
\tstd::vector<ArkFile> g_ark_prev;

"""
ANCHOR = "\t// =========================================================== мониторинг v2"
i = s.index(ANCHOR)
j = s.index("\n", i) + 1
s = s[:j] + "\n" + DECLS + s[j:]

io.open(P, "w", encoding="utf-8", newline="\r\n").write(s)
print("общие объявления собраны вверху блока")
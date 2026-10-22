# -*- coding: utf-8 -*-
# Два фикса CmdBpTrace:
#  1) mode 0: печатать счётчик вызовов ДО обнуления (иначе вечно 0);
#  2) mode 1: повторное включение поверх активного — «уже включён», не сканировать
#     заново (после первой подмены Func != ProcessInternal и patched=0).
import io

CPP = r'C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp'
src = io.open(CPP, encoding='utf-8', newline='').read()
NL = '\r\n' if '\r\n' in src else '\n'


def blk(t):
    return t.replace('\n', NL)


# --- фикс 1
old1 = blk('''			g_bp_on.store(false, std::memory_order_relaxed);
			const size_t n = g_bp_targets.size();
			BpRemovePatch();
			BpResetCounters();
			LogLine(S("bptrace: выключен (вызовов {}), подмен снят с {} UFunction", g_bp_calls.load(), n));''')
new1 = blk('''			g_bp_on.store(false, std::memory_order_relaxed);
			const size_t n = g_bp_targets.size();
			const int64_t done = g_bp_calls.load();
			BpRemovePatch();
			BpResetCounters();
			LogLine(S("bptrace: выключен (с {} включения вызовов {}), подмен снят с {} UFunction",
				win_dur_ms() / 1000, done, n));''')
if old1 not in src:
    raise SystemExit('фикс 1: якорь не найден')
src = src.replace(old1, new1, 1)

# --- фикс 2: helper dur + идемпотентность
old2 = blk('''		if (mode == 2)
		{
			const BpScanResult r = BpScanAndPatch(false);''')
new2 = blk('''		if (mode == 2)
		{
			const BpScanResult r = BpScanAndPatch(false);''')
assert old2 in src
# helper: длительность окна (мс с начала текущего окна)
helper = blk('''	int64_t win_dur_ms()
	{
		const int64_t t = GetTickCount64() - g_bp_win_start.load();
		return t > 0 ? t : 0;
	}
''')
i = src.index('\tvoid CmdBpTrace(RCONClientConnection*, RCONPacket* packet, UWorld*)')
src = src[:i] + helper + src[i:]

old3 = blk('''		if (InCooldown())
		{
			LogLine(S("bptrace: отказ - пауза после сэмплер-окна ещё не кончилась ({} с)",
				CooldownLeft()));
			return;
		}
		const BpScanResult r = BpScanAndPatch(true);''')
new3 = blk('''		if (g_bp_on.load(std::memory_order_relaxed))
		{
			LogLine("bptrace: уже включён (подмена активна) - окно продолжается, счётчики не тронуты");
			return;
		}
		if (InCooldown())
		{
			LogLine(S("bptrace: отказ - пауза после сэмплер-окна ещё не кончилась ({} с)",
				CooldownLeft()));
			return;
		}
		const BpScanResult r = BpScanAndPatch(true);''')
if old3 not in src:
    raise SystemExit('фикс 2: якорь не найден')
src = src.replace(old3, new3, 1)

io.open(CPP, 'w', encoding='utf-8', newline='').write(src)
print('оба фикса внесены')

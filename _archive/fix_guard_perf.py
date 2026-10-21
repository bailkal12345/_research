import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(p, encoding="utf-8").read()

# 1) опкод MOV byte ptr [RSI+disp32], imm8 = C6 86 <disp32> <imm8> — 7 байт,
#    непосредственный операнд (target) отстоит от C6 на 6 байт, а не на 4.
old_guard = '''		if (target[-4] != 0xC6 || target[-3] != 0x86 || target[-2] != 0x30 || target[-1] != 0x02)
		{
			char buf[80];
			snprintf(buf, sizeof(buf), "%02X %02X %02X %02X %02X", target[-4], target[-3],
				target[-2], target[-1], target[0]);
			LogLine(S("concurrent: неожиданные байты [{}], патч отменён", buf));
			return;
		}'''
new_guard = '''		// C6 86 30 02 00 00 <imm8>: непосредственный операнд — 7-й байт,
		// то есть со смещением -6 от начала инструкции.
		if (target[-6] != 0xC6 || target[-5] != 0x86 || target[-4] != 0x30 || target[-3] != 0x02 ||
			target[-2] != 0x00 || target[-1] != 0x00)
		{
			char buf[96];
			snprintf(buf, sizeof(buf), "%02X %02X %02X %02X %02X %02X %02X", target[-6], target[-5],
				target[-4], target[-3], target[-2], target[-1], target[0]);
			LogLine(S("concurrent: неожиданные байты [{}], патч отменён", buf));
			return;
		}'''
assert old_guard in s
s = s.replace(old_guard, new_guard)

# 2) GetThreadTimes на псевдо-ручке GetCurrentThread() в этой системе
#    возвращает время всего процесса — берём настоящий HANDLE потока.
old_perf = '''		FILETIME ct, et, kt, ut;
		if (!GetThreadTimes(GetCurrentThread(), &ct, &et, &kt, &ut))
			return;'''
new_perf = '''		FILETIME ct, et, kt, ut;
		HANDLE th = g_perf.thread;
		if (!th)
			return;
		if (!GetThreadTimes(th, &ct, &et, &kt, &ut))
			return;'''
assert old_perf in s
s = s.replace(old_perf, new_perf)

s = s.replace('''		std::atomic<int> window{0};
	};
	Perf g_perf;''', '''		std::atomic<int> window{0};
		HANDLE thread = nullptr;
	};
	Perf g_perf;''')

s = s.replace('''	void CmdPerf(RCONClientConnection*, RCONPacket* packet, UWorld*)
	{
		const int32_t seconds = ArgInt(packet, 20);''', '''	void CmdPerf(RCONClientConnection*, RCONPacket* packet, UWorld*)
	{
		const int32_t seconds = ArgInt(packet, 20);
		if (!g_perf.thread && g_game_tid.load())
		{
			g_perf.thread = OpenThread(THREAD_QUERY_INFORMATION, FALSE, g_game_tid.load());
			LogLine(S("perf: handle потока {}", g_perf.thread ? "получен" : "НЕ удался"));
		}''')
io.open(p, "w", encoding="utf-8").write(s)
print("ok")

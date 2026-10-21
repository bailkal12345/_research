import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(p, encoding="utf-8").read()

old = '''		// страховка: убеждаемся, что патчим именно тот опкод
		if (target[-2] != 0x00 || target[-1] != 0x02 || target[-3] != 0x86 || target[-4] != 0xC6)
		{
			LogLine(S("concurrent: unexpected bytes at 0x{:X}, abort",
				static_cast<unsigned long long>(PATCH_CONCURRENT_RVA)));
			return false;
		}'''
new = '''		// страховка: C6 86 30 02 00 00 00 = MOV byte ptr [RSI+0x230], imm8;
		// непосредственный операнд — последний байт, он и есть флаг.
		if (target[-4] != 0xC6 || target[-3] != 0x86 || target[-2] != 0x30 || target[-1] != 0x02)
		{
			char buf[80];
			snprintf(buf, sizeof(buf), "op = %02X %02X %02X %02X %02X %02X %02X", target[-4],
				target[-3], target[-2], target[-1], target[0], target[1], target[2]);
			LogLine(S("concurrent: неожиданные байты [{}], патч отменён", buf));
			return false;
		}'''
assert old in s
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8").write(s)
print("ok")

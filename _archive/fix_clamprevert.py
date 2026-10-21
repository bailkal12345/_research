import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(p, encoding="utf-8").read()
old = '''		if (target[-1] != 0xB9 || std::memcmp(target, CLAMP_OLD, 4) != 0)
		{
			// уже пропатчено?
			if (target[-1] == 0xB9 && std::memcmp(target, CLAMP_NEW, 4) == 0)
			{
				LogLine(S("tickclamp: уже поднят до 100000"));
				if (!raise)
					return true;
			}
			else
			{
				LogLine(S("tickclamp: неожиданные байты, патч отменён"));
				return false;
			}
		}'''
new = '''		if (target[-1] != 0xB9)
		{
			LogLine(S("tickclamp: неожиданный опкод, патч отменён"));
			return false;
		}
		if (std::memcmp(target, CLAMP_OLD, 4) == 0 && !raise)
		{
			LogLine(S("tickclamp: уже штатные 120"));
			return true;
		}
		if (std::memcmp(target, CLAMP_NEW, 4) == 0 && raise)
		{
			LogLine(S("tickclamp: уже поднят до 100000"));
			return true;
		}
		if (std::memcmp(target, CLAMP_OLD, 4) != 0 && std::memcmp(target, CLAMP_NEW, 4) != 0)
		{
			LogLine(S("tickclamp: байты не те и не другие, патч отменён"));
			return false;
		}'''
assert old in s
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8").write(s)
print("fixed")

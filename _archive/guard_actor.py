import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(p, encoding="utf-8").read()
old = '''		if (pattern.empty())
		{
			LogLine(S("actortickoff: нужно указать подстроку класса"));
			return;
		}'''
new = '''		if (pattern.empty())
		{
			LogLine(S("actortickoff: нужно указать подстроку класса"));
			return;
		}
		// Проверено: массовое выключение тиков у акторов роняет сервер
		// (GameThread зависает, RCON не отвечает). Команда заблокирована,
		// как и cull — из неё нет безопасного выхода.
		if (body.find("force") == std::string::npos)
		{
			LogLine(S("actortickoff: отклонено — выключение тиков акторов проверено "
				"и роняет сервер. Используйте overlaptrim и кэши."));
			return;
		}'''
assert old in s
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8").write(s)
print("ok")

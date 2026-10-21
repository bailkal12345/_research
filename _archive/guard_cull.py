import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(p, encoding="utf-8").read()
old = '''		const float radius = static_cast<float>(ArgInt(packet, 0));
		if (radius > 0.0f && !g_cull_hook_installed)'''
new = '''		// Требуется явное подтверждение: проверено, что отсечение акторов по
		// расстоянию роняет сервер (на радиусе 15 км GameThread зависает и RCON
		// перестаёт отвечать). Поэтому включать только осознанно.
		const std::string body = packet->Body.ToString();
		if (body.find("force") == std::string::npos && ArgInt(packet, 0) > 0)
		{
			LogLine(S("cull: отклонено — команда опасна, требует 'force'. "
				"Отсечение тиков акторов проверено: сервер зависает. Используйте "
				"overlaptrim и кэши."));
			return;
		}
		const float radius = static_cast<float>(ArgInt(packet, 0));
		if (radius > 0.0f && !g_cull_hook_installed)'''
assert old in s
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8").write(s)
print("ok")

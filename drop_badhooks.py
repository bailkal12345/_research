import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(p, encoding="utf-8").read()
# опасные хуки: подписи неизвестны, установка FillLevelList вешает сервер
s = s.replace('''		{"FTickTaskManager.FillLevelList", reinterpret_cast<LPVOID>(H_FillLevelList),
		reinterpret_cast<LPVOID*>(&_o_FillLevelList)},
		{"FTickTaskLevel.QueueAllTicks", reinterpret_cast<LPVOID>(H_QueueAllTicks),
		reinterpret_cast<LPVOID*>(&_o_QueueAllTicks)},
		{"FTickTaskLevel.QueueNewlySpawned", reinterpret_cast<LPVOID>(H_QueueNewlySpawned),
		reinterpret_cast<LPVOID*>(&_o_QueueNewlySpawned)},
''','''		// ВНИМАНИЕ: хуки на FillLevelList / QueueAllTicks / QueueNewlySpawned
		// не ставятся — подписи неизвестны, а установка FillLevelList вешает
		// сервер. Диспетчер измеряется через флаг окна StartFrame.
''')
io.open(p, "w", encoding="utf-8").write(s)
print("ok")

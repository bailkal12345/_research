import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(p, encoding="utf-8").read()
# вынести константы UPrimitiveComponent выше по файлу
s = s.replace('''	// --------------------------------------------- overlaptrim v3 с белой меткой''',
'''	// UPrimitiveComponent: OverlappingComponents (TArray) @ +1312,
	//                      bGenerateOverlapEvents = бит 10 в dword @ +500.
	constexpr int PRIM_OVERLAPPING = 1312;
	constexpr int PRIM_FLAGS = 500;
	constexpr uint32_t PRIM_GENERATE_OVERLAP = 1u << 10;

	// --------------------------------------------- overlaptrim v3 с белой меткой''')
# убрать дубликаты в исходном месте
s = s.replace('''	// UPrimitiveComponent: OverlappingComponents (TArray) @ +1312,
	//                      bGenerateOverlapEvents = бит 10 в dword @ +500.
	// Компонент с сотнями пересечений даёт O(n^2) на каждое новое событие,
	// поэтому такие компоненты можно отключать целиком.
	constexpr int PRIM_OVERLAPPING = 1312;
	constexpr int PRIM_FLAGS = 500;
	constexpr uint32_t PRIM_GENERATE_OVERLAP = 1u << 10;
''','''	// Компонент с сотнями пересечений даёт O(n^2) на каждое новое событие,
	// поэтому такие компоненты можно отключать целиком.
''')
io.open(p, "w", encoding="utf-8").write(s)
print("ok")

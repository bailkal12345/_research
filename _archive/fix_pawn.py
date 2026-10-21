import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(p, encoding="utf-8").read()
s = s.replace('''			// контроллер без Pawn — наблюдатель, его не считаем
			void* pawn = *reinterpret_cast<void**>(reinterpret_cast<char*>(pc) + 0x2E8);''',
'''			// AController::Pawn @ +1176 (PDB). Контроллер без Pawn — наблюдатель.
			void* pawn = *reinterpret_cast<void**>(reinterpret_cast<char*>(pc) + 1176);''')
io.open(p, "w", encoding="utf-8").write(s)
print("offset fixed")

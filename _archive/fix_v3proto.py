import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(p, encoding="utf-8").read()
# прототип обхода компонентов рядом с константами
s = s.replace('''	constexpr uint32_t PRIM_GENERATE_OVERLAP = 1u << 10;

	// --------------------------------------------- overlaptrim v3 с белой меткой''',
'''	constexpr uint32_t PRIM_GENERATE_OVERLAP = 1u << 10;
	void ForEachPrimitiveComponent(const std::function<void(UPrimitiveComponent*)>& fn);

	// --------------------------------------------- overlaptrim v3 с белой меткой''')
io.open(p, "w", encoding="utf-8").write(s)
print("ok")

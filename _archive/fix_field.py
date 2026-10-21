import io
p = "fieldcheck.cpp"
s = io.open(p, encoding="utf-8").read()
s = s.replace('''	// ищем UDT по имени среди верхнего уровня
	IDiaEnumSymbols* top = nullptr;
	session->get_globalScope(&top);''',
'''	// ищем UDT по имени среди верхнего уровня
	IDiaSymbol* global = nullptr;
	session->get_globalScope(&global);
	IDiaEnumSymbols* top = nullptr;
	if (global)
		global->findChildrenEx(SymTagUDT, nullptr, nsNone, &top);''')
s = s.replace("if (t == SymTagUDT || t == SymTagStruct || t == SymTagClass)", "if (t == SymTagUDT)")
s = s.replace('''		LONG loc = 0;
		DWORD bitpos = 0, length = 0;
		f->get_location(&loc);
		f->get_bitPosition(&bitpos);
		f->get_bitLength(&length);
		BSTR nm = nullptr;
		f->get_name(&nm);
		DWORD vt = 0;
		f->get_type(&vt);''',
'''		DWORD loc = 0;
		DWORD bitpos = 0, length = 0;
		f->get_location(&loc);
		f->get_bitPosition(&bitpos);
		f->get_locationType(&length);
		BSTR nm = nullptr;
		f->get_name(&nm);''')
s = s.replace('''		if (show)
			printf("%-8ld %-6u %ls (type 0x%X, bits %u)\\n", loc, bitpos, nm ? nm : L"?", vt, length);''',
'''		if (show)
			printf("offset=%-6u bits=%-6u locType=%-4u %ls\\n", loc, bitpos, length, nm ? nm : L"?");''')
io.open(p, "w", encoding="utf-8").write(s)
print("ok")

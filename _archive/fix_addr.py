import io
p = "addrcheck.cpp"
s = io.open(p, encoding="utf-8").read()
s = s.replace('#include <cstdio>', '#include <cstdio>\n#include <cstring>')
s = s.replace('''	HRESULT hr = NoRegCoCreate(dia ? Widen(dia).c_str() : L"msdia140.dll", CLSID_DiaSource,
		IID_IDiaDataSource, (void**)&src);''',
'''	const std::wstring dia_path = dia ? Widen(dia) : std::wstring(L"msdia140.dll");
	HRESULT hr = NoRegCoCreate(dia_path.c_str(), CLSID_DiaSource, IID_IDiaDataSource, (void**)&src);''')
s = s.replace('''			LONG len = 0;
			sym->get_length(&len);''', '''			ULONGLONG len = 0;
			sym->get_length(&len);''')
s = s.replace('(long)len', '(unsigned long long)len')
io.open(p, "w", encoding="utf-8").write(s)
print("ok")

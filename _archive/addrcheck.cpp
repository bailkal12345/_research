// addrcheck.cpp — сверяет, что именно ArkApi берёт из PDB для имени функции.
//
// ArkApi (Offsets.cpp) строит адрес как (GetModuleHandle(nullptr) + OptionalHeader.BaseOfCode)
// + "offset", а offset берёт из IDiaSymbol::get_addressOffset(). Здесь печатаем
// addressOffset рядом с relativeVirtualAddress, чтобы понять, какая из величин
// соответствует реальному RVA функции в образе.
#include <windows.h>
#include <cvconst.h>
#include <dia2.h>
#include <diacreate.h>

#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

static std::wstring Widen(const char* s)
{
	return std::wstring(s, s + strlen(s));
}

int main(int argc, char** argv)
{
	if (argc < 3)
	{
		printf("usage: addrcheck <pdb> <name> [name...]\n");
		return 1;
	}

	CoInitializeEx(nullptr, COINIT_MULTITHREADED);

	IDiaDataSource* src = nullptr;
	const char* dia_env = getenv("DIA_DLL");
	const std::wstring dia_path = dia_env ? Widen(dia_env) : std::wstring(L"msdia140.dll");
	HRESULT hr = NoRegCoCreate(dia_path.c_str(), CLSID_DiaSource, IID_IDiaDataSource, (void**)&src);
	if (FAILED(hr))
	{
		printf("create failed 0x%08X\n", hr);
		return 2;
	}

	hr = src->loadDataFromPdb(Widen(argv[1]).c_str());
	if (FAILED(hr))
	{
		printf("loadDataFromPdb failed 0x%08X\n", hr);
		return 3;
	}

	IDiaSession* session = nullptr;
	src->openSession(&session);
	IDiaSymbol* global = nullptr;
	session->get_globalScope(&global);

	for (int i = 2; i < argc; ++i)
	{
		const std::wstring want = Widen(argv[i]);
		IDiaEnumSymbols* en = nullptr;
		global->findChildrenEx(SymTagFunction, want.c_str(), nsCaseInsensitive, &en);
		IDiaSymbol* sym = nullptr;
		ULONG count = 0;
		while (en && S_OK == en->Next(1, &sym, &count) && count == 1)
		{
			DWORD addr_off = 0, rva = 0;
			sym->get_addressOffset(&addr_off);
			sym->get_relativeVirtualAddress(&rva);
			ULONGLONG len = 0;
			sym->get_length(&len);
			BSTR nm = nullptr;
			sym->get_name(&nm);
			printf("%-40s addressOffset=0x%08X  rva=0x%08X  len=%ld  name=%ls\n", argv[i], addr_off,
				rva, (unsigned long long)len, nm ? nm : L"?");
			if (nm)
				SysFreeString(nm);
			sym->Release();
		}
		if (en)
			en->Release();
	}
	return 0;
}
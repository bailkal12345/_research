// fieldcheck.cpp — печатает поля структуры из PDB с их смещениями и битами.
//
// Нужно, чтобы выставить FTickFunction::bRunOnAnyThread прямо в памяти:
// ArkApi отдаёт имена полей, но не даёт битовые позиции внутри битфилда.
//
//   fieldcheck <pdb> <StructName> [FieldName...]
#include <windows.h>
#include <cvconst.h>
#include <dia2.h>
#include <diacreate.h>

#include <cstdio>
#include <cstring>
#include <string>

static std::wstring Widen(const char* s)
{
	return std::wstring(s, s + strlen(s));
}

int main(int argc, char** argv)
{
	if (argc < 3)
	{
		printf("usage: fieldcheck <pdb> <Struct> [field...]\n");
		return 1;
	}

	CoInitializeEx(nullptr, COINIT_MULTITHREADED);

	const char* dia_env = getenv("DIA_DLL");
	const std::wstring dia_path = dia_env ? Widen(dia_env) : std::wstring(L"msdia140.dll");
	IDiaDataSource* src = nullptr;
	if (FAILED(NoRegCoCreate(dia_path.c_str(), CLSID_DiaSource, IID_IDiaDataSource, (void**)&src)))
	{
		printf("create dia failed\n");
		return 2;
	}
	if (FAILED(src->loadDataFromPdb(Widen(argv[1]).c_str())))
	{
		printf("loadDataFromPdb failed\n");
		return 3;
	}

	IDiaSession* session = nullptr;
	src->openSession(&session);

	// ищем UDT по имени среди верхнего уровня
	IDiaSymbol* global = nullptr;
	session->get_globalScope(&global);
	IDiaEnumSymbols* top = nullptr;
	if (global)
		global->findChildrenEx(SymTagUDT, nullptr, nsNone, &top);

	IDiaSymbol* udt = nullptr;
	DWORD tag = 0;
	ULONG cnt = 0;
	while (top && S_OK == top->Next(1, &udt, &cnt) && cnt == 1)
	{
		DWORD t = 0;
		udt->get_symTag(&t);
		if (t == SymTagUDT)
		{
			BSTR nm = nullptr;
			udt->get_name(&nm);
			const bool match = nm && Widen(argv[2]).compare(nm) == 0;
			if (nm)
				SysFreeString(nm);
			if (match)
				break;
		}
		udt = nullptr;
	}

	if (!udt)
	{
		printf("struct %s not found\n", argv[2]);
		return 4;
	}

	printf("== %s ==\n", argv[2]);
	printf("%-8s %-6s %s\n", "offset", "bit", "field");

	IDiaEnumSymbols* fields = nullptr;
	udt->findChildrenEx(SymTagData, nullptr, nsNone, &fields);
	IDiaSymbol* f = nullptr;
	while (fields && S_OK == fields->Next(1, &f, &cnt) && cnt == 1)
	{
		LONG loc = 0;
		DWORD bitpos = 0, length = 0;
		f->get_offset(&loc);
		f->get_bitPosition(&bitpos);
		f->get_locationType(&length);  // 1=isOffset, бит-поле отдельно
		BSTR nm = nullptr;
		f->get_name(&nm);

		// фильтр по запрошенным именам, если они есть
		bool show = argc < 4;
		for (int i = 3; i < argc; ++i)
		{
			if (nm && Widen(argv[i]).compare(nm) == 0)
				show = true;
		}
		if (show)
			printf("offset=%-6ld bits=%-6u locType=%-4u %ls\n", loc, bitpos, length, nm ? nm : L"?");
		if (nm)
			SysFreeString(nm);
		f->Release();
	}
	return 0;
}
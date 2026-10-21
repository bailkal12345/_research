// pdbsym.cpp — выгрузка всех функций и глобальных переменных из .pdb через DIA.
//
//   pdbsym.exe <ShooterGameServer.pdb> <out.tsv>
//
// Формат: name \t rva \t size \t tag
// Функции обходятся рекурсивно по namespace/class/struct/union/interface/module,
// внутри хранятся только Function (и Data у верхнего уровня — глобалы).
// Имена берутся недемонглированные (UWorld::Tick), RVA — из PDB, они уже
// вычитаны на PreferredLoadAddress, поэтому совпадают с RVA в образе.
#include <windows.h>
#include <dbghelp.h>

#include <cvconst.h>
#include <dia2.h>
#include <diacreate.h>

#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

static IDiaDataSource* g_source = nullptr;
static IDiaSession* g_session = nullptr;
static IDiaSymbol* g_global = nullptr;
static FILE* g_out = nullptr;
static long long g_funcs = 0;
static long long g_datas = 0;

static void Clean(const char* s)
{
	// в TSV: заменяем табуляции и переводы строк
	for (const char* p = s; *p; ++p)
	{
		if (*p == '\t' || *p == '\n' || *p == '\r')
		{
			fputc(' ', g_out);
		}
		else
		{
			fputc(*p, g_out);
		}
	}
}

static std::string Narrow(BSTR b)
{
	if (b == nullptr)
	{
		return {};
	}
	UINT n = SysStringLen(b);
	std::string out;
	out.reserve(n);
	for (UINT i = 0; i < n; ++i)
	{
		wchar_t c = b[i];
		out.push_back(c < 128 ? static_cast<char>(c) : '?');
	}
	return out;
}

static void Emit(IDiaSymbol* sym, DWORD tag)
{
	LONG rva = 0;
	DWORD rva_d = 0;
	if (FAILED(sym->get_relativeVirtualAddress(&rva_d)) || rva_d == 0)
	{
		return;
	}
	rva = static_cast<LONG>(rva_d);
	ULONGLONG len = 0;
	sym->get_length(&len);

	BSTR name = nullptr;
	if (FAILED(sym->get_name(&name)) || name == nullptr || *name == L'\0')
	{
		return;
	}

	BSTR pretty = nullptr;
	std::string out_name;
	if (SUCCEEDED(sym->get_undecoratedNameEx(UNDNAME_NAME_ONLY, &pretty)) && pretty)
	{
		out_name = Narrow(pretty);
		SysFreeString(pretty);
	}
	if (out_name.empty())
	{
		out_name = Narrow(name);
	}
	SysFreeString(name);
	if (out_name.empty())
	{
		return;
	}

	if (tag == SymTagFunction)
	{
		++g_funcs;
	}
	else
	{
		++g_datas;
	}

	fwrite(out_name.data(), 1, out_name.size(), g_out);
	fprintf(g_out, "\t%ld\t%llu\t%d\n", (long)rva, (unsigned long long)len, (int)tag);
}

static void WalkFunctions(IDiaSymbol* parent)
{
	IDiaEnumSymbols* en = nullptr;
	if (FAILED(parent->findChildrenEx(SymTagFunction, nullptr, nsNone, &en)) || en == nullptr)
	{
		return;
	}
	IDiaSymbol* child = nullptr;
	ULONG count = 0;
	while (S_OK == en->Next(1, &child, &count) && count == 1)
	{
		Emit(child, SymTagFunction);
		child->Release();
	}
	en->Release();
}

static void Walk(IDiaSymbol* parent)
{
	IDiaEnumSymbols* en = nullptr;
	if (FAILED(parent->findChildrenEx(SymTagNull, nullptr, nsNone, &en)) || en == nullptr)
	{
		return;
	}

	IDiaSymbol* child = nullptr;
	ULONG count = 0;
	while (S_OK == en->Next(1, &child, &count) && count == 1)
	{
		DWORD tag = SymTagNull;
		if (SUCCEEDED(child->get_symTag(&tag)))
		{
			switch (tag)
			{
			case SymTagFunction:
				Emit(child, SymTagFunction);
				break;

			case SymTagUDT:
			case SymTagEnum:
			case SymTagCompiland:
			case SymTagExe:
			case SymTagPublicSymbol:
				Walk(child);
				break;

			case SymTagNull:
				// в этой версии cvconst.h тега SymTagNamespace нет: namespace
				// приходит как SymTagNull без RVA. Спускаемся только туда.
				{
					DWORD child_rva = 1;
					if (SUCCEEDED(child->get_relativeVirtualAddress(&child_rva)) && child_rva == 0)
					{
						Walk(child);
					}
				}
				break;

			default:
				break;
			}
		}
		child->Release();
	}
	en->Release();
}

static void WalkGlobalData(IDiaSymbol* global)
{
	IDiaEnumSymbols* en = nullptr;
	if (SUCCEEDED(global->findChildrenEx(SymTagData, nullptr, nsNone, &en)) && en)
	{
		IDiaSymbol* child = nullptr;
		ULONG count = 0;
		while (S_OK == en->Next(1, &child, &count) && count == 1)
		{
			Emit(child, SymTagData);
			child->Release();
		}
		en->Release();
	}
}

int main(int argc, char** argv)
{
	if (argc < 3)
	{
		printf("usage: pdbsym <pdb> <out.tsv>\n");
		return 1;
	}

	// Путь должен жить до конца main: указатель на локальный std::wstring,
	// вышедший из скоупа, даёт пустую строку и 0x806D0005 от DIA.
	const std::string pdb_arg = argv[1];
	const std::wstring pdb_path(pdb_arg.begin(), pdb_arg.end());

	// MTA: с STA (CoInitialize) DIA на этом .pdb бросает 0x806D0005 — проверено.
	CoInitializeEx(nullptr, COINIT_MULTITHREADED);

	// msdia140.dll берём из Binaries рядом с игрой: он умеет читать этот PDB,
// а свежий DIA из Visual Studio 18 падает с 0x806D0005.
	wchar_t dia_path[512] = {};
	const char* env = getenv("DIA_DLL");
	if (env)
	{
		size_t n = strlen(env);
		for (size_t i = 0; i < n && i < 511; ++i)
		{
			dia_path[i] = (wchar_t)(unsigned char)env[i];
		}
		dia_path[n] = 0;
	}
	else
	{
		wcscpy_s(dia_path, L"msdia140.dll");
	}

	// Диагностика: тот же PDB пробуем несколькими путями — как в probe.cpp.
	{
		wchar_t shortp[512] = {};
		GetShortPathNameW(pdb_path.c_str(), shortp, 512);
		printf("pdb    : %ls\n", pdb_path);
		printf("short  : %ls\n", shortp);
		printf("dia    : %ls\n", dia_path);
	}

	HRESULT hr = NoRegCoCreate(dia_path, CLSID_DiaSource, IID_IDiaDataSource, (void**)&g_source);
	if (FAILED(hr))
	{
		printf("NoRegCoCreate failed 0x%08X\n", hr);
		return 2;
	}

	hr = g_source->loadDataFromPdb(pdb_path.c_str());
	if (FAILED(hr))
	{
		printf("loadDataFromPdb failed 0x%08X\n", hr);
		return 3;
	}

	hr = g_source->openSession(&g_session);
	if (FAILED(hr))
	{
		printf("openSession failed 0x%08X\n", hr);
		return 4;
	}

	hr = g_session->get_globalScope(&g_global);
	if (FAILED(hr))
	{
		printf("get_globalScope failed 0x%08X\n", hr);
		return 5;
	}

	std::wstring out_path(argv[2], argv[2] + strlen(argv[2]));
	g_out = _wfopen(out_path.c_str(), L"wt");
	if (g_out == nullptr)
	{
		printf("cannot open output\n");
		return 6;
	}

	WalkGlobalData(g_global);
	Walk(g_global);

	fflush(g_out);
	fclose(g_out);
	printf("functions=%lld data=%lld\n", g_funcs, g_datas);

	if (g_global)
		g_global->Release();
	if (g_session)
		g_session->Release();
	if (g_source)
		g_source->Release();
	CoUninitialize();
	return 0;
}
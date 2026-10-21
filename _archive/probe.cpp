// probe.cpp — на каком именно .pdb ломается loadDataFromPdb и чем именно.
#include <windows.h>
#include <cvconst.h>
#include <dia2.h>
#include <diacreate.h>

#include <cstdio>
#include <string>

static void Try(const wchar_t* dia_path, const char* label, const wchar_t* pdb)
{
	IDiaDataSource* src = nullptr;
	HRESULT hr = NoRegCoCreate(dia_path, CLSID_DiaSource, IID_IDiaDataSource, (void**)&src);
	if (FAILED(hr) || src == nullptr)
	{
		printf("%-28s create failed 0x%08X\n", label, hr);
		return;
	}

	hr = src->loadDataFromPdb(pdb);
	printf("%-28s load  0x%08X", label, hr);
	if (SUCCEEDED(hr))
	{
		IDiaSession* session = nullptr;
		if (SUCCEEDED(src->openSession(&session)) && session)
		{
			IDiaSymbol* global = nullptr;
			if (SUCCEEDED(session->get_globalScope(&global)) && global)
			{
				BSTR ver = nullptr;
				global->get_name(&ver);
				printf("  name=%ls", ver ? ver : L"?");
				if (ver)
				{
					SysFreeString(ver);
				}
				global->Release();
			}
			session->Release();
		}
	}
	printf("\n");
	src->Release();
}

int main(int argc, char** argv)
{
	CoInitializeEx(nullptr, COINIT_MULTITHREADED);

	const wchar_t* pdb_local = L"C:\\asmdata\\Servers\\Server1\\ShooterGame\\Binaries\\Win64\\ShooterGameServer.pdb";
	wchar_t short_path[512] = {};
	GetShortPathNameW(pdb_local, short_path, 512);
	wchar_t local_upper[512] = {};
	wcscpy_s(local_upper, pdb_local);
	for (wchar_t* p = local_upper; *p; ++p)
	{
		if (*p >= L'a' && *p <= L'z')
			*p -= 32;
	}

	const wchar_t* dia_local = L"C:\\asmdata\\Servers\\Server1\\ShooterGame\\Binaries\\Win64\\msdia140.dll";

	printf("short path: %ls\n", short_path);
	printf("--- DIA из каталога игры:\n");
	Try(dia_local, "local full", pdb_local);
	Try(dia_local, "local UPPER", local_upper);
	Try(dia_local, "local short", short_path);
	Try(dia_local, "local cwd-rel", L"ShooterGameServer.pdb");
	printf("--- DIA из System32 (по умолчанию):\n");
	Try(L"msdia140.dll", "default full", pdb_local);
	printf("--- другие PDB:\n");
	Try(dia_local, "v358 server", L"C:\\asmdata\\Servers\\Server2\\ShooterGame\\Binaries\\Win64\\ShooterGameServer.pdb");
	Try(dia_local, "v361 client", L"C:\\Games\\ARK_SE_game_v361\\ShooterGame\\Binaries\\Win64\\ShooterGame.pdb");
	return 0;
}
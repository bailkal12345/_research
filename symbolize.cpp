// Symbolize RVAs of a module against a PDB (dbghelp with tracing).
// Usage: symbolize.exe <base> <pdbPath> <rva> [<rva> ...]
#include <windows.h>
#include <dbghelp.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#pragma comment(lib, "dbghelp.lib")

static BOOL CALLBACK TraceCallback(HANDLE, ULONG ac, ULONG64 data, ULONG64)
{
	if (ac == CBA_EVENT)
	{
		const IMAGEHLP_CBA_EVENT* e = reinterpret_cast<const IMAGEHLP_CBA_EVENT*>(static_cast<size_t>(data));
		if (e && e->desc)
			printf("[dbg] %s\n", e->desc);
	}
	return FALSE;
}

int main(int argc, char** argv)
{
	if (argc < 5)
	{
		printf("usage: symbolize <ModuleName> <base> <searchDir> <rva>...\n");
		return 1;
	}
	const char* modname = argv[1];
	const ULONGLONG base = strtoull(argv[2], nullptr, 0);
	const char* searchDir = argv[3];
	HANDLE proc = GetCurrentProcess();
	SymSetOptions(SYMOPT_UNDNAME | SYMOPT_DEBUG);
	SymRegisterCallback64(proc, &TraceCallback, 0);
	if (!SymInitialize(proc, searchDir, FALSE))
	{
		printf("SymInitialize failed %lu\n", GetLastError());
		return 2;
	}
	const ULONGLONG mod = SymLoadModuleEx(proc, nullptr, modname, nullptr, base, 0, nullptr, 0);
	if (!mod)
	{
		printf("SymLoadModuleEx failed %lu\n", GetLastError());
		return 2;
	}
	printf("module handle: 0x%llX\n", mod);
	SYMBOL_INFOW* sym = static_cast<SYMBOL_INFOW*>(calloc(1, sizeof(SYMBOL_INFOW) + 512 * sizeof(wchar_t)));
	for (int i = 3; i < argc; ++i)
	{
		const ULONGLONG rva = strtoull(argv[i], nullptr, 0);
		sym->SizeOfStruct = sizeof(SYMBOL_INFOW);
		sym->MaxNameLen = 512;
		ULONGLONG disp = 0;
		printf("rva 0x%llX: ", rva);
		if (SymFromAddrW(proc, base + rva, &disp, sym))
			printf("%ws +0x%llX\n", sym->Name, disp);
		else
			printf("?(err %lu)\n", GetLastError());
	}
	return 0;
}

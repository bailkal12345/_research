# -*- coding: utf-8 -*-
# doit6 §4 (исправление): безопасный перебор UFunction.
#
# ЧТО БЫЛО: перебор через Globals::GUObjectArray()() - в этой сборке движка поле
# "Global.GUObjectArray" НЕ резолвится ArkApi (DataValue -> nullptr) => AV, игровой
# поток падал (наблюдалось: RCON перестаёт отвечать, CPU простаивает).
#
# КАК НАДО: Globals::GetObjectsOfClass(UClass*, TArray<UObject*>*, ...) - штатный
# и безопасный API движка. Класс UFunction берём через "UFunction.StaticClass".
# Дополнительно весь скан обёрнут в SEH (__try/__except) - при любой ошибке
# в переборе команда вернёт ошибку, а не уронит игровой поток.
import io

CPP = r'C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp'
src = io.open(CPP, 'r', encoding='utf-8', newline='').read()
NL = '\r\n' if '\r\n' in src else '\n'


def blk(t):
    return t.replace('\n', NL)


OLD = blk('''	// Перебор UObject: у скриптовых UFunction поле Func == &ProcessInternal.
	BpScanResult BpScanAndPatch(bool apply)
	{
		BpScanResult res;
		void* mod = GetModuleHandleW(L"ShooterGameServer.exe");
		if (!mod)
			return res;
		g_bp_orig_processinternal = (void*)((uint8_t*)mod + BPTRACE_PROCESSINTERNAL_RVA);

		const FUObjectArray& arr = Globals::GUObjectArray()();
		const int count = arr.ObjObjects.NumElements;
		for (int i = 0; i < count; ++i)
		{
			UObject* obj = arr.ObjObjects.GetObjectPtr(i)->Object;
			if (!obj)
				continue;
			void** func_slot = reinterpret_cast<void**>(reinterpret_cast<uint8_t*>(obj) + UFUNCTION_FUNC_OFFSET);
			void* f = *func_slot;
			if (!f || f != g_bp_orig_processinternal)
				continue;
			// Func == &ProcessInternal => это скриптовая (Blueprint) UFunction.
			++res.script_functions;
			++res.ufunctions_seen;
			if (!apply)
				continue;
			bool known = false;
			for (size_t k = 0; k < g_bp_targets.size(); ++k)
			{
				if (g_bp_targets[k] == (void*)obj)
				{
					known = true;
					break;
				}
			}
			if (known)
			{
				++res.already;
				continue;
			}
			g_bp_targets.push_back((void*)obj);
			g_bp_orig_func.push_back(f);
			*func_slot = (void*)&BpHandler;
			++res.patched;
		}
		return res;
	}''')

NEW = blk('''	// Перебор UFunction: штатный API движка GetObjectsOfClass + SEH-защита.
	// (Ранее использовался Globals::GUObjectArray()() - в этой сборке поле
	//  "Global.GUObjectArray" не резолвится ArkApi => AV и падение игрового потока.)
	BpScanResult BpScanAndPatch(bool apply)
	{
		BpScanResult res;
		void* mod = GetModuleHandleW(L"ShooterGameServer.exe");
		if (!mod)
			return res;
		g_bp_orig_processinternal = (void*)((uint8_t*)mod + BPTRACE_PROCESSINTERNAL_RVA);

		UClass* fn_class = NativeCall<UClass*>(nullptr, "UFunction.StaticClass");
		if (!fn_class)
		{
			res.error = "UFunction.StaticClass не разрешился";
			return res;
		}
		TArray<UObject*> fns;
		__try
		{
			Globals::GetObjectsOfClass(fn_class, &fns, true, EObjectFlags::RF_Transient);
		}
		__except (EXCEPTION_EXECUTE_HANDLER)
		{
			res.error = "исключение при GetObjectsOfClass";
			return res;
		}
		res.ufunctions_seen = fns.Num();
		for (int32_t i = 0; i < fns.Num(); ++i)
		{
			UObject* obj = fns[i];
			if (!obj)
				continue;
			void** func_slot = reinterpret_cast<void**>(reinterpret_cast<uint8_t*>(obj) + UFUNCTION_FUNC_OFFSET);
			void* f = nullptr;
			__try
			{
				f = *func_slot;
			}
			__except (EXCEPTION_EXECUTE_HANDLER)
			{
				continue;
			}
			if (!f || f != g_bp_orig_processinternal)
				continue;
			// Func == &ProcessInternal => это скриптовая (Blueprint) UFunction.
			++res.script_functions;
			if (!apply)
				continue;
			bool known = false;
			for (size_t k = 0; k < g_bp_targets.size(); ++k)
			{
				if (g_bp_targets[k] == (void*)obj)
				{
					known = true;
					break;
				}
			}
			if (known)
			{
				++res.already;
				continue;
			}
			g_bp_targets.push_back((void*)obj);
			g_bp_orig_func.push_back(f);
			__try
			{
				*func_slot = (void*)&BpHandler;
			}
			__except (EXCEPTION_EXECUTE_HANDLER)
			{
				g_bp_targets.pop_back();
				g_bp_orig_func.pop_back();
				continue;
			}
			++res.patched;
		}
		return res;
	}''')

assert OLD in src, 'старый перебор не найден'
src = src.replace(OLD, NEW, 1)

# в структуре результата - поле error
src = src.replace(blk('''	struct BpScanResult
	{
		int ufunctions_seen = 0;
		int script_functions = 0;
		int patched = 0;
		int already = 0;
	};'''), blk('''	struct BpScanResult
	{
		int ufunctions_seen = 0;
		int script_functions = 0;
		int patched = 0;
		int already = 0;
		const char* error = nullptr;
	};'''), 1)

# вывод ошибки в команде
src = src.replace(blk('''		if (mode == 2)
		{
			const BpScanResult r = BpScanAndPatch(false);
			LogLine(S("bptrace: перечисление: скриптовых UFunction (Func==&ProcessInternal) = {}",
				r.script_functions));
			return;
		}
		const BpScanResult r = BpScanAndPatch(true);
		LogLine(S("bptrace: подмена Func у {} скриптовых UFunction", r.patched));'''),
                  blk('''		if (mode == 2)
		{
			const BpScanResult r = BpScanAndPatch(false);
			if (r.error)
			{
				LogLine(S("bptrace: ошибка перечисления: {}", r.error));
				return;
			}
			LogLine(S("bptrace: перечисление: UFunction всего={} скриптовых(Func==&ProcessInternal)={}",
				r.ufunctions_seen, r.script_functions));
			return;
		}
		const BpScanResult r = BpScanAndPatch(true);
		if (r.error)
		{
			LogLine(S("bptrace: ошибка подмены: {}", r.error));
			return;
		}
		LogLine(S("bptrace: подмена Func у {} скриптовых UFunction (всего UFunction={})",
			r.patched, r.ufunctions_seen));'''), 1)

io.open(CPP, 'w', encoding='utf-8', newline='').write(src)
print('перебор переведён на GetObjectsOfClass + SEH-защиту')

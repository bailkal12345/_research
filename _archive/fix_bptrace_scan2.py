# -*- coding: utf-8 -*-
# Замена тела BpScanAndPatch на безопасную версию (GetObjectsOfClass + SEH).
import io, re

CPP = r'C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp'
src = io.open(CPP, 'r', encoding='utf-8', newline='').read()
NL = '\r\n' if '\r\n' in src else '\n'


def blk(t):
    return t.replace('\n', NL)


# границы функции: от сигнатуры до закрывающей скобки на уровне отступа
i = src.index('\tBpScanResult BpScanAndPatch(bool apply)')
j = src.index('\n\tvoid BpRemovePatch()', i)
old = src[i:j]
print('--- заменяемый блок (%d символов) ---' % len(old))
print(old[:400])

NEW = blk('''	BpScanResult BpScanAndPatch(bool apply)
	{
		BpScanResult res;
		void* mod = GetModuleHandleW(L"ShooterGameServer.exe");
		if (!mod)
			return res;
		g_bp_orig_processinternal = (void*)((uint8_t*)mod + BPTRACE_PROCESSINTERNAL_RVA);

		// Перебор UFunction: штатный API движка. Раньше использовался
		// Globals::GUObjectArray()(), но в этой сборке поле "Global.GUObjectArray"
		// не резолвится ArkApi (DataValue -> nullptr) => AV и падение игрового потока.
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
			// Func == &ProcessInternal => скриптовая (Blueprint) UFunction.
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
			__try
			{
				g_bp_targets.push_back((void*)obj);
				g_bp_orig_func.push_back(f);
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
	}
''')

src = src[:i] + NEW + src[j:]

# поле error в структуре результата
if 'const char* error = nullptr;' not in src:
    src = src.replace(blk('''		int patched = 0;
		int already = 0;
	};'''), blk('''		int patched = 0;
		int already = 0;
		const char* error = nullptr;
	};'''), 1)

# вывод ошибки
src = src.replace(blk('''			LogLine(S("bptrace: перечисление: скриптовых UFunction (Func==&ProcessInternal) = {}",
				r.script_functions));'''),
                  blk('''			if (r.error)
			{
				LogLine(S("bptrace: ошибка перечисления: {}", r.error));
				return;
			}
			LogLine(S("bptrace: перечисление: UFunction всего={} скриптовых(Func==&ProcessInternal)={}",
				r.ufunctions_seen, r.script_functions));'''), 1)

src = src.replace(blk('''		LogLine(S("bptrace: подмена Func у {} скриптовых UFunction", r.patched));'''),
                  blk('''		if (r.error)
		{
			LogLine(S("bptrace: ошибка подмены: {}", r.error));
			return;
		}
		LogLine(S("bptrace: подмена Func у {} скриптовых UFunction (всего UFunction={})",
			r.patched, r.ufunctions_seen));'''), 1)

io.open(CPP, 'w', encoding='utf-8', newline='').write(src)
print('тело перебора заменено')

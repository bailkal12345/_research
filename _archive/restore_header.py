import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
s = io.open(p, encoding="utf-8").read()
header = '''// TickProf — профилировщик и инструмент распараллеливания GameThread
// для ARK: Survival Evolved v361 (плагин ArkApi).
//
// Состав:
//   * фазовые таймеры на хуках (UWorld.Tick, RunTickGroup, NetDriver, GC, ...);
//   * сэмплирующий профилировщик GameThread (SuspendThread + GetThreadContext,
//     символизация офлайн по PDB);
//   * патч bAllowConcurrentTicks (снимает запрет UE4.5 на асинхронные тики);
//   * разметка тик-функций флагом bRunOnAnyThread;
//   * кэш Kismet-канвасов и счётчик overlap-событий по владельцам.
//
// Команды (RCON и консоль), полный список — в конце файла.
#include <windows.h>
#include <Psapi.h>

#include <API/ARK/Ark.h>
#include <Logger/Logger.h>
#include <Tools.h>

#include <atomic>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <initializer_list>
#include <mutex>
#include <string>
#include <thread>
#include <type_traits>
#include <vector>
#include <algorithm>

namespace
{
	constexpr const char* PLUGIN_NAME = "TickProf";

	void VerifyConcurrent();
'''
# заменяем первую строку файла (старую пролог-потерю) на полный заголовок
lines = s.split("\n")
assert "Кэш UCanvas" in lines[1], lines[1]
out = header.split("\n") + lines[1:]
io.open(p, "w", encoding="utf-8").write("\n".join(out))
print("header restored")

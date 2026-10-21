# -*- coding: utf-8 -*-
"""Заменяет HookTable() (most vexing parse) на статический массив g_hooks."""
import io
import re

CPP = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
src = io.open(CPP, encoding="utf-8").read()

table = re.search(r"\tHookDesc HookTable\(HK_TOTAL\)\s*\n\t\{\s*\n\t\treturn \{.*?\n\t\t\};\s*\n\t\}\n", src, re.S)
assert table, "HookTable not found"

replacement = """\tconst HookDesc g_hooks[HK_TOTAL] = {
\t\t{"FEngineLoop.Tick", reinterpret_cast<LPVOID>(H_EngineLoopTick),
\t\t reinterpret_cast<LPVOID*>(&_o_EngineLoopTick)},
\t\t{"UEngine.Tick", reinterpret_cast<LPVOID>(H_UEngineTick), reinterpret_cast<LPVOID*>(&_o_UEngineTick)},
\t\t{"UWorld.Tick", reinterpret_cast<LPVOID>(H_UWorldTick), reinterpret_cast<LPVOID*>(&_o_UWorldTick)},
\t\t{"UWorld.RunTickGroup", reinterpret_cast<LPVOID>(H_RunTickGroup),
\t\t reinterpret_cast<LPVOID*>(&_o_RunTickGroup)},
\t\t{"FTickTaskManager.StartFrame", reinterpret_cast<LPVOID>(H_StartFrame),
\t\t reinterpret_cast<LPVOID*>(&_o_StartFrame)},
\t\t{"FTickTaskManager.EndFrame", reinterpret_cast<LPVOID>(H_EndFrame),
\t\t reinterpret_cast<LPVOID*>(&_o_EndFrame)},
\t\t{"UNetDriver.TickDispatch", reinterpret_cast<LPVOID>(H_NetTickDispatch),
\t\t reinterpret_cast<LPVOID*>(&_o_NetTickDispatch)},
\t\t{"UObject.CollectGarbage", reinterpret_cast<LPVOID>(H_CollectGarbage),
\t\t reinterpret_cast<LPVOID*>(&_o_CollectGarbage)},
\t};
"""
src = src[: table.start()] + replacement + src[table.end() :]

src = src.replace("\t\tHookDesc t = HookTable();\n", "")
src = re.sub(r"\bt\[id\]\.", "g_hooks[id].", src)
src = src.replace('LogLine(S("hooks: {} ({})", PLUGIN_NAME, list));', 'LogLine(S("hooks: {}", PLUGIN_NAME, list));')

io.open(CPP, "w", encoding="utf-8").write(src)
print("ok")
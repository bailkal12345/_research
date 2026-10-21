# -*- coding: utf-8 -*-
"""Переводит вызовы Log::GetLog()->info/warn/error(...) в LogLine(S(...)) + добавляет S()/ArgToStr."""
import re
import io

CPP = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
src = io.open(CPP, encoding="utf-8").read()

HELPERS = r'''
#include <sstream>
#include <type_traits>

namespace
{
	template <class T>
	std::string ArgToStr(T&& v)
	{
		using D = std::decay_t<T>;
		std::ostringstream ss;
		if constexpr (std::is_same_v<D, bool>)
		{
			ss << (v ? "yes" : "no");
		}
		else if constexpr (std::is_pointer_v<D>)
		{
			if (!v)
				ss << "nullptr";
			else
			{
				std::ostringstream t;
				t << "0x" << std::hex << reinterpret_cast<uintptr_t>(v);
				ss << t.str();
			}
		}
		else if constexpr (std::is_same_v<D, const char*>)
		{
			ss << (v ? v : "(null)");
		}
		else if constexpr (std::is_arithmetic_v<D>)
		{
			ss << v;
		}
		else
		{
			ss << v;
		}
		return ss.str();
	}

	// Мини-форматтер: "{}" на каждый следующий аргумент.
	template <class... Ts>
	std::string S(const char* fmt, Ts... args)
	{
		std::vector<std::string> parts;
		parts.reserve(sizeof...(Ts));
		(void)std::initializer_list<int>{ (parts.push_back(ArgToStr(args)), 0)... };

		std::string out;
		size_t ai = 0;
		for (const char* p = fmt; *p; ++p)
		{
			if (p[0] == '{' && p[1] == '}')
			{
				out += ai < parts.size() ? parts[ai] : std::string("{}");
				++ai;
				++p;
			}
			else
			{
				out.push_back(*p);
			}
		}
		return out;
	}
} // namespace
'''

# вставляем помощники сразу после "namespace\n{"
anchor = "namespace\n{\n"
assert anchor in src
src = src.replace(anchor, anchor + HELPERS + "\n", 1)

# Log::GetLog()->X("[{}] ...", args);   ->   LogLine(S("...", args));
pattern = re.compile(
    r'Log::GetLog\(\)->(?:info|warn|error)\(\"\[(?:\{\})\] ?(.*?)\"((?:, [^;]*?)?)\);',
    re.S,
)


def repl(m: "re.Match") -> str:
    fmt = m.group(1)
    args = m.group(2).strip()
    if args.startswith(","):
        args = args[1:].strip()
    call = f'S("{fmt}"'
    if args:
        call += ", " + args
    call += ")"
    return f"LogLine({call});"


src, n = pattern.subn(repl, src)
io.open(CPP, "w", encoding="utf-8").write(src)
print("replaced:", n)
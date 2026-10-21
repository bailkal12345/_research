import io
p = r"C:\Dev\ARK-Server-Plugins\TickProf\TickProf\TickProf.cpp"
lines = io.open(p, encoding="utf-8").read().split("\n")
# строка 536 (1-based): "\t}\t\tif (g_wait_stacks)" -> разнести и закрытие перенести вниз
assert lines[535].strip().startswith("}") and "g_wait_stacks" in lines[535], repr(lines[535])
lines[535] = "\t\tif (g_wait_stacks)"
# найти конец блока: строка с delete[] g_wait_stacks; после неё закрыть функцию
for j in range(536, len(lines)):
    if "delete[] g_wait_stacks" in lines[j]:
        # на следующих строках: g_wait_stacks = nullptr; }  -> добавить ещё одну }
        k = j
        while "g_wait_stacks = nullptr;" not in lines[k]:
            k += 1
        # строка k+1 должна быть "\t\t}" (конец if) — добавить "\t}" после неё
        assert lines[k+1].strip() == "}", repr(lines[k+1])
        lines.insert(k+2, "\t}")
        break
io.open(p, "w", encoding="utf-8").write("\n".join(lines))
print("исправлено")

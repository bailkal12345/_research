import io, re, collections
src = r"C:\Dev\ARK_SE_code_dump\game_aquatica.c"
# тело APrimalDinoCharacter::Tick: начиная с определения, до закрывающей скобки на уровне 0
start = None
with io.open(src, encoding="utf-8", errors="replace") as f:
    lines = f.readlines()
for i, ln in enumerate(lines):
    if ln.startswith("void __thiscall APrimalDinoCharacter::Tick(") or ln.startswith("void APrimalDinoCharacter::Tick("):
        start = i
        break
print("Tick начинается со строки", start)
calls = collections.Counter()
depth = 0
seen = False
n = 0
for i in range(start, min(start + 200000, len(lines))):
    s = lines[i].rstrip("\n")
    if s.strip() == "{":
        depth += 1
        seen = True
    elif s.strip() == "}" or s.strip() == "};":
        depth -= 1
        if seen and depth == 0:
            print("Tick заканчивается на строке", i, "длина", i - start)
            break
    if seen and depth >= 1:
        for m in re.finditer(r"\b([A-Za-z_][\w:]*)\s*\(", s):
            nm = m.group(1)
            if nm and nm not in ("if","while","for","switch","return","sizeof","for_each"):
                calls[nm] += 1
                n += 1
print("вызовов всего:", n)
for nm, c in calls.most_common(28):
    print("   %-58s %d" % (nm[:58], c))

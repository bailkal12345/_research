import io, re, collections
p = r"C:\Dev\ARK_SE_code_dump\game_aquatica.c"
fun_re = re.compile(r"^([A-Za-z_][\w \*:<>,]*?)\s+([A-Za-z_][\w:]*)\((.*)\)\s*$")
total = 0
named = 0
samples = []
names = collections.Counter()
with io.open(p, encoding="utf-8", errors="replace") as f:
    for ln in f:
        if not ln or ln[0] not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_":
            continue
        m = fun_re.match(ln.rstrip("\n"))
        if not m:
            continue
        ret, name, args = m.groups()
        if ret in ("typedef", "struct", "union", "enum", "static_assert"):
            continue
        total += 1
        if "::" in name or (not name.startswith("FUN_") and not name.startswith("sub_")):
            named += 1
            if len(samples) < 25:
                samples.append(ln.strip()[:150])
        names[name.split("::")[0]] += 1
print("всего определений функций:", total)
print("с осмысленными именами (не FUN_):", named)
print()
for s in samples:
    print("  ", s)
print()
print("топ префиксов имён:")
for n, c in names.most_common(25):
    print("   %-40s %d" % (n[:40], c))

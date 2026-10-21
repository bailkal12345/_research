import io, re, collections, json
src = r"C:\Dev\ARK_SE_code_dump\game_aquatica.c"
fun_re = re.compile(r"^([A-Za-z_][\w \*:<>,]*?)\s+([A-Za-z_][\w:~<>*&]*)\((.*)\)\s*$")
cur = None
counts = collections.Counter()
lines_in = collections.Counter()
i = 0
with io.open(src, encoding="utf-8", errors="replace") as f:
    for ln in f:
        s = ln.rstrip("\n")
        if cur is None:
            c = s[:1]
            if c and (c.isalpha() or c == "_"):
                m = fun_re.match(s)
                if m and m.group(1) not in ("typedef","struct","union","enum","static_assert","extern"):
                    cur = m.group(2)
                    counts.setdefault(cur, 0)
                    lines_in.setdefault(cur, 0)
        else:
            if s == "}":
                cur = None
            else:
                lines_in[cur] += 1
                if "AddUniqueImpl" in s:
                    counts[cur] += 1
        i += 1
multi = [(n, c, lines_in[n]) for n, c in counts.items() if c >= 2]
multi.sort(key=lambda x: -x[1])
print("функций с >=2 AddUniqueImpl:", len(multi))
print("всего вызовов AddUniqueImpl:", sum(counts.values()))
print()
for n, c, ln in multi[:25]:
    print("   %-62s %3d вызовов, %5d строк" % (n[:62], c, ln))
io.open("addunique_hot.json","w",encoding="utf-8").write(json.dumps([[n,c,ln] for (n,c),ln in counts.items() if c], ensure_ascii=False))

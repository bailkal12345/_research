import io, re, json, os, time
src = r"C:\Dev\ARK_SE_code_dump\game_aquatica.c"
idx = {}
fun_re = re.compile(r"^([A-Za-z_][\w \*:<>,]*?)\s+([A-Za-z_][\w:~<>*&]*)\((.*)\)\s*$")
t0 = time.time()
cur = None
with io.open(src, encoding="utf-8", errors="replace") as f:
    for i, ln in enumerate(f):
        s = ln.rstrip("\n")
        if not s:
            continue
        c = s[0]
        if c in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_":
            m = fun_re.match(s)
            if m:
                ret, name, args = m.groups()
                if ret not in ("typedef","struct","union","enum","static_assert","extern"):
                    full = name
                    if "::" in name:
                        # адрес функции уже есть в имени FUN_ -> полное имя выше по стеку
                        pass
                    idx.setdefault(name, i)
        if s == "{" and cur is None:
            pass
print("уникальных имён:", len(idx), "за %.0f с" % (time.time()-t0))
io.open("dump_index.json","w",encoding="utf-8").write(json.dumps(idx))

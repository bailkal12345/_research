import io, itertools
p = r"C:\Dev\ARK_SE_code_dump\game_aquatica.c"
with io.open(p, encoding="utf-8", errors="replace") as f:
    for ln in itertools.islice(f, 60):
        print(repr(ln)[:200])

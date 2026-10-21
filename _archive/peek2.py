import io
p = r"C:\Dev\ARK_SE_code_dump\game_aquatica.c"
n = 0
with io.open(p, encoding="utf-8", errors="replace") as f:
    for i, ln in enumerate(f):
        if ln.startswith("// Function") or ln.startswith("int64_t ") or ln.startswith("void "):
            print(i, repr(ln)[:160])
            n += 1
            if n > 12:
                break
print("...")

import io
src = r"C:\Dev\ARK_SE_code_dump\game_aquatica.c"
targets = [2582412]
with io.open(src, encoding="utf-8", errors="replace") as f:
    for i, ln in enumerate(f):
        if 2582340 <= i <= 2582412 and ln.strip():
            print(i, ln.rstrip()[:150])
        if i > 2582412:
            break

import io, json
src = r"C:\Dev\ARK_SE_code_dump\game_aquatica.c"
idx = json.load(io.open("dump_index.json", encoding="utf-8"))
for k in sorted(idx):
    if "APrimalDinoCharacter::Tick" in k or "APrimalCharacter::Tick" in k or "ANPCZoneManager::" in k and "Tick" in k:
        print("%-70s %s" % (k[:70], idx[k]))
print("---")
with io.open(src, encoding="utf-8", errors="replace") as f:
    for i, ln in enumerate(f):
        if 5791694 <= i <= 5791740:
            print(i, ln.rstrip()[:160])
        if i > 5791745:
            break

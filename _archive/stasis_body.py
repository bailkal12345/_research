import io, re
src = r"C:\Dev\ARK_SE_code_dump\game_aquatica.c"
KEYS = ("SetTickFunctionEnable","SetActorTickEnabled","TickInterval","bTickEnabled","SetComponentTickEnabled",
        "PrimaryActorTick","Unstasis","Stasis")
with io.open(src, encoding="utf-8", errors="replace") as f:
    lines = f.readlines()
for start, tag in ((3005735, "APrimalCharacter::Stasis"), (3101785, "APrimalDinoCharacter::Stasis")):
    # найти конец тела по балансу скобок
    depth = 0; seen = False; out = []
    for i in range(start, min(start + 1200, len(lines))):
        s = lines[i].rstrip()
        if s.strip() == "{": depth += 1; seen = True
        elif s.strip() in ("}", "};"): depth -= 1
        if seen:
            if any(k in s for k in KEYS) or s.strip() in ("{", "}", "};"):
                out.append("%7d %s" % (i, s.strip()[:120]))
        if seen and depth == 0: break
    print("=== %s (строк %d..%d, тело %d строк)" % (tag, start, i, i-start))
    for ln in out[:26]:
        print("   ", ln)
    print()

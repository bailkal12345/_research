import io
# анализатор: определять RIP как syscall-заглушку по модулям, а не по значению
p = "waitstack.py"
s = io.open(p, encoding="utf-8").read()
s = s.replace('''    print("=== RIP: адреса системного вызова ===")
    for rip, c in rips.most_common(6):
        print("   %5.1f%%  %016X" % (100.0 * c / count, rip))''','''    # имена модулей, чтобы отличать заглушки вызовов от работы движка
    mods = []
    if os.path.exists(mods_path := args.path.rsplit(".", 1)[0] + ".modules.txt"):
        with open(mods_path, encoding="utf-8", errors="replace") as f:
            next(f, None)
            for ln in f:
                p2 = ln.split("\\t")
                if len(p2) >= 3:
                    s0 = int(p2[0], 16)
                    mods.append((s0, s0 + int(p2[1], 16), p2[2].split("\\\\")[-1]))

    def modof(v):
        for s0, e0, n in mods:
            if s0 <= v < e0:
                return n
        return "ядро"

    print("=== RIP: где именно заблокирован поток ===")
    agg = collections.Counter()
    for rip, c in rips.items():
        agg[modof(rip)] += c
    for n, c in agg.most_common(8):
        print("   %5.1f%%  %s" % (100.0 * c / count, n))
    print()
    for rip, c in rips.most_common(8):
        print("   %5.1f%%  %016X  %s" % (100.0 * c / count, rip, modof(rip)))''')
io.open(p, "w", encoding="utf-8").write(s)
print("ok")

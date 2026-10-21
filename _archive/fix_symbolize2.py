import io
p = "symbolize.py"
s = io.open(p, encoding="utf-8").read()
s = s.replace('''    ap.add_argument("--exclude-idle", action="store_true",''',
'''    ap.add_argument("--modules", default="", help="prof_*.modules.txt рядом с профилем")
    ap.add_argument("--exclude-idle", action="store_true",''')
s = s.replace('''    mods = sorted(live_modules(args.pid)) if args.pid else []''',
'''    mods = []
    mod_file = args.modules
    if not mod_file:
        cand = args.bin.rsplit(".", 1)[0] + ".modules.txt"
        mod_file = cand if os.path.exists(cand) else ""
    if mod_file and os.path.exists(mod_file):
        with open(mod_file, "r", encoding="utf-8", errors="replace") as f:
            next(f, None)
            for line in f:
                parts = line.rstrip("\\n").split("\\t")
                if len(parts) < 3:
                    continue
                try:
                    start = int(parts[0], 16)
                    size = int(parts[1], 16)
                except ValueError:
                    continue
                mods.append((start, start + size, parts[2].split("\\\\")[-1]))
    elif args.pid:
        mods = live_modules(args.pid)
    mods = sorted(mods)''')
s = s.replace("import argparse\nimport bisect", "import argparse\nimport bisect\nimport os")
io.open(p, "w", encoding="utf-8").write(s)
print("patched symbolize")

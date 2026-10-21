import io
p = "exp_idle.py"
s = io.open(p, encoding="utf-8").read()
old = '''        total += 1
        if not (nt_base <= ctx.Rip < nt_end):
            time.sleep(args.interval)
            continue
        idle_hits += 1'''
new = '''        total += 1
        rip = ctx.Rip
        in_game = base <= rip < base + 0x8000000
        in_ntdll = nt_base <= rip < nt_end
        # Поток, блокированный в системном вызове, показывает в CONTEXT не адрес
        # ntdll, а адрес ядерного стаба (KiSystemServiceUser, 0xFFFFF8xx).
        # Поэтому ожидание опознаём по «RIP вне пользовательских модулей».
        if in_game or not (rip > 0x7FF000000000):
            time.sleep(args.interval)
            continue
        idle_hits += 1'''
assert old in s
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8").write(s)
print("ok")

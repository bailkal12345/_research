import io
p = r"C:\Dev\_research\exp_ledger.py"
s = io.open(p, encoding="utf-8").read()
s = s.replace("for h in range(0, 8):", "for h in range(0, 5):")
io.open(p, "w", encoding="utf-8").read() if False else io.open(p, "w", encoding="utf-8").write(s)
print("ok")

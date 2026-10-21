import io
p = r"C:\Dev\_research\slot_measure.py"
s = io.open(p, encoding="utf-8", newline="").read()
s = s.replace("def saveworld_freeze():", "def saveworld_freeze(runs=2):")
s = s.replace("    out = []\n    for _ in range(2):", "    out = []\n    for _ in range(runs):")
io.open(p, "w", encoding="utf-8", newline="").write(s)
import ast; ast.parse(s); print("saveworld_freeze(runs) ок")

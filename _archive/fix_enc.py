import io, re
p = r"C:\Dev\_research\watch_shift.py"
s = io.open(p, encoding="utf-8", newline="").read()
# во всех subprocess.run добавить явную кодировку
s = s.replace('capture_output=True, text=True, timeout=1500)',
              'capture_output=True, text=True, encoding="utf-8",\n                           errors="replace", timeout=1500)')
s = s.replace('capture_output=True, text=True, timeout=slot_min * 60)',
              'capture_output=True, text=True, encoding="utf-8",\n                           errors="replace", timeout=slot_min * 60)')
s = s.replace('capture_output=True, text=True,\n                           encoding="utf-8", errors="replace", timeout=120)',
              'capture_output=True, text=True,\n                           encoding="utf-8", errors="replace", timeout=120)')
s = s.replace('capture_output=True, text=True, timeout=180)',
              'capture_output=True, text=True, encoding="utf-8",\n                       errors="replace", timeout=180)')
# в deploy(): отдавать больше хвоста, чтобы был виден трейсбек
s = s.replace('tail = out.strip().splitlines()[-6:]', 'tail = out.strip().splitlines()[-12:]')
io.open(p, "w", encoding="utf-8", newline="").write(s)
import ast; ast.parse(s)
print("watch_shift.py: кодировка исправлена")

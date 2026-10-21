import io
p = "exp_idle.py"
s = io.open(p, encoding="utf-8").read()
s = s.replace("    pid = find_pid()\n", "    try:\n        import threadcpu\n        pid = threadcpu.find_pid()\n    except Exception:\n        pid = 0\n")
io.open(p, "w", encoding="utf-8").write(s)
print("ok")

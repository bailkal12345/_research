import io
p = "exp_idle.py"
s = io.open(p, encoding="utf-8").read()
s = s.replace("        pid = threadcpu.find_pid()",
              "        pid = threadcpu.find_pid()\n        if isinstance(pid, (list, tuple)):\n            pid = pid[0] if pid else 0")
io.open(p, "w", encoding="utf-8").write(s)
print("ok")

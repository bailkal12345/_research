import io
p = r"C:\Dev\_research\patch_mon.py"
s = io.open(p, encoding="utf-8").read()
old = 'old_tick = """\t\tg_perf.frames.fetch_add(1, std::memory_order_relaxed);\n\t\tg_perf.cpu100ns.store(k + u, std::memory_order_relaxed);\n"""'
new = 'old_tick = "\\t\\tg_perf.frames.fetch_add(1, std::memory_order_relaxed);\\n\\t\\tg_perf.cpu100ns.store(k + u, std::memory_order_relaxed);\\n"'
assert old in s, "old_tick literal not found"
s = s.replace(old, new, 1)
io.open(p, "w", encoding="utf-8").write(s)
print("old_tick переведён на escape")

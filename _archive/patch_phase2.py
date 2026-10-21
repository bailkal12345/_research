import io
p = "exp_phase2.py"
s = io.open(p, encoding="utf-8").read()
s = s.replace('''    print("\\n[6] патч bAllowConcurrentTicks + разметка тиков", flush=True)
    cmd("TickProf.fix concurrent 1")
    time.sleep(6)
    show(("concurrent",))
    results["patch"] = measure("PATCH", tid, 40)
    if results["patch"] and not results["patch"]["alive"]:
        return 6''','''    print("\\n[6] патч bAllowConcurrentTicks (A/B/A)", flush=True)
    cmd("TickProf.fix concurrent 1")
    time.sleep(6)
    show(("concurrent",))
    results["patch_A"] = measure("PATCH_A", tid, 40)
    if results["patch_A"] and not results["patch_A"]["alive"]:
        return 6
    cmd("TickProf.fix concurrent 0")
    time.sleep(6)
    show(("concurrent",))
    results["patch_B"] = measure("PATCH_OFF", tid, 40)''')
io.open(p, "w", encoding="utf-8").write(s)
print("ok")

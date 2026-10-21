import io
p = "run_measure.py"
src = io.open(p, encoding="utf-8").read()

src = src.replace('''HOOKS = [
    (0, "FEngineLoop.Tick"),
    (1, "UEngine.Tick"),
    (3, "UWorld.RunTickGroup"),
    (4, "FTickTaskManager.StartFrame"),
    (5, "FTickTaskManager.EndFrame"),
    (6, "UNetDriver.TickDispatch"),
    (7, "Global.CollectGarbage"),
    (8, "AShooterGameMode.Tick"),
    (9, "AShooterGameState.Tick"),
    (10, "UNetDriver.TickFlush"),
    (11, "UWorld.TickNetClient"),
    (2, "UWorld.Tick"),  # последним: его держит сам ArkApi
]''', '''# Порядок важен: сначала безопасные хуки внутри тика мира, потом внешние обвязки.
# FEngineLoop.Tick (0) при проверке ронял сервер — идёт последним и только по --risky.
HOOKS = [
    (3, "UWorld.RunTickGroup"),
    (4, "FTickTaskManager.StartFrame"),
    (5, "FTickTaskManager.EndFrame"),
    (6, "UNetDriver.TickDispatch"),
    (7, "Global.CollectGarbage"),
    (8, "AShooterGameMode.Tick"),
    (9, "AShooterGameState.Tick"),
    (10, "UNetDriver.TickFlush"),
    (11, "UWorld.TickNetClient"),
    (1, "UEngine.Tick"),
    (2, "UWorld.Tick"),
]
RISKY = [(0, "FEngineLoop.Tick")]''')

src = src.replace('''    print("[step] installing hooks one by one", flush=True)''',
'''    # ---- фаза 1: чистое сэмплирование, без единого патча ----
    print("[step] phase 1: sampling WITHOUT hooks for %.0f s" % args.sample_seconds, flush=True)
    print("  start: %s" % cmd("TickProf.start"), flush=True)
    t_end = time.time() + args.sample_seconds
    while time.time() < t_end:
        time.sleep(5)
    print("  stop: %s" % cmd("TickProf.stop"), flush=True)
    time.sleep(3)
    print("  status: %s" % cmd("TickProf.status"), flush=True)

    # ---- фаза 2: фазовые таймеры через хуки ----
    print("[step] phase 2: installing hooks one by one", flush=True)''')

src = src.replace('''    print("[step] sampling for %.0f s" % args.sample_seconds, flush=True)
    print("  start: %s" % cmd("TickProf.start"), flush=True)
    samples = []
    t_end = time.time() + args.sample_seconds
    while time.time() < t_end:
        c = threadcpu.cpu_times(tid)
        if c:
            samples.append(c)
        time.sleep(5)
    print("[step] stopping", flush=True)
    print("  stop: %s" % cmd("TickProf.stop"), flush=True)
    time.sleep(3)''',
'''    if args.risky:
        print("[step] risky hooks", flush=True)
        for idx, name in RISKY:
            print("  -> hook %-2d %s" % (idx, name), flush=True)
            print("     rcon: %s" % cmd("TickProf.hook %d" % idx), flush=True)
            time.sleep(4)
            c, ok = alive(tid, base)
            print("     game thread cpu=%.3f s/s -> %s" % (c, "ok" if ok else "DEAD?"), flush=True)
            if not ok:
                break

    print("[step] sampling with hooks for %.0f s" % args.sample_seconds, flush=True)
    print("  start: %s" % cmd("TickProf.start"), flush=True)
    t_end = time.time() + args.sample_seconds
    while time.time() < t_end:
        time.sleep(5)
    print("  stop: %s" % cmd("TickProf.stop"), flush=True)
    time.sleep(3)''')

src = src.replace('''    ap.add_argument("--skip-load", action="store_true")''',
'''    ap.add_argument("--risky", action="store_true", help="в конце проверить и FEngineLoop.Tick")''')

io.open(p, "w", encoding="utf-8").write(src)
print("patched")

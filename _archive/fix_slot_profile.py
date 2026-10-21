import io
p = r"C:\Dev\_research\slot_measure.py"
s = io.open(p, encoding="utf-8", newline="").read()

prof_block = '''    binp = profile(60)
    res["profile"] = os.path.basename(binp) if binp else ""
    res["top20"] = top_symbols(binp, 20)
    cmd("TickProf.ticklist")
    cmd("TickProf.ticksets")
    cmd("TickProf.overlapsizes")
    time.sleep(20)
    res["censuses"] = [ln.split(" ", 1)[-1] for ln in log_tail(60)
                       if any(k in ln for k in ("ticklist:", "ticksets:", "overlapsizes:"))]

'''
assert prof_block in s, "блок профиля не найден"
s = s.replace(prof_block, "", 1)

tail_old = '''    res["finished"] = datetime.datetime.now().isoformat(timespec="seconds")
    _save(res, args.map)
    print("ИТОГ сохранён", flush=True)
    return 0'''
tail_new = '''    # ---- профиль и переписи ПОСЛЕДНИМИ ----
    # На Genesis профилёр (TickProf.start 60) ронял сервер сразу после сэмпла:
    # все .bin/.ret/.wait успевали записаться, но процесс умирал без крашстака
    # и без дампа. Если такое повторится, П0/П1 и П2/П3 уже сохранены.
    if args.profile:
        print("профиль и переписи (последним шагом)", flush=True)
        binp = profile(60)
        res["profile"] = os.path.basename(binp) if binp else ""
        res["top20"] = top_symbols(binp, 20)
        cmd("TickProf.ticklist")
        cmd("TickProf.ticksets")
        cmd("TickProf.overlapsizes")
        time.sleep(20)
        res["censuses"] = [ln.split(" ", 1)[-1] for ln in log_tail(60)
                           if any(k in ln for k in ("ticklist:", "ticksets:", "overlapsizes:"))]
        ok, why = health(crash_mark)
        res["alive_after_profile"] = ok
        print("   после профиля: %s" % why, flush=True)

    res["finished"] = datetime.datetime.now().isoformat(timespec="seconds")
    _save(res, args.map)
    print("ИТОГ сохранён", flush=True)
    return 0'''
assert tail_old in s
s = s.replace(tail_old, tail_new, 1)
s = s.replace('    ap.add_argument("--warmup", type=int, default=300)',
              '    ap.add_argument("--warmup", type=int, default=300)\n'
              '    ap.add_argument("--no-profile", dest="profile", action="store_false",\n'
              '                    help="не снимать профиль (он роняет сервер на Genesis)")')
io.open(p, "w", encoding="utf-8", newline="").write(s)
import ast; ast.parse(s)
print("слот: профиль перенесён в конец, флаг --no-profile добавлен")

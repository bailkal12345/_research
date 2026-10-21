import io
p = r"C:\Dev\_research\slot_measure.py"
s = io.open(p, encoding="utf-8", newline="").read()

helpers = '''
ARK_DIR = r"C:\\asmdata\\Servers\\Server1\\ShooterGame\\Saved\\SavedArks"


def ark_state(card):
    """Слепок файлов сейва: автосохранение меняет mtime/size .ark и .bak.

    Нужен, потому что AutoSavePeriodMinutes=15, а сохранение мира на этом
    сейве занимает минуты и полностью искажает ms CPU/тик: в профиле Genesis
    00:28 весь исполняемый код — это сериализация (SerializeTaggedProperties,
    FSaveFileObjectWriter, UWorld::SaveToFile).
    """
    out = {}
    try:
        for n in os.listdir(ARK_DIR):
            low = n.lower()
            if low.endswith(".ark") or "anticorruption" in low:
                f = os.path.join(ARK_DIR, n)
                try:
                    out[n] = (os.path.getmtime(f), os.path.getsize(f))
                except OSError:
                    pass
    except OSError:
        pass
    return out


def save_idle(card, quiet=90, limit=900):
    """Ждёт, пока сохранение мира закончится (файлы не меняются quiet секунд)."""
    end = time.time() + limit
    last, since = ark_state(card), time.time()
    while time.time() < end:
        cur = ark_state(card)
        if cur != last:
            print("   сохранение мира идёт (%s)" % ",".join(sorted(cur)), flush=True)
            last, since = cur, time.time()
        elif time.time() - since >= quiet:
            return True
        time.sleep(15)
    return False

'''
anchor = "def health(crash_mark):"
assert anchor in s
s = s.replace(anchor, helpers.lstrip("\n") + "\n" + anchor, 1)

# window(): пометить окно как искажённое, если сейв писался внутри него
old = '''    ok, why = health(crash_mark)
    tps = frames / wall if wall else 0.0
    return {"tps": tps, "cpu": (c0 + c1) / 2.0,
            "ms_tick": 1000.0 * (c0 + c1) / 2.0 / tps if tps else 0.0, "healthy": ok, "why": why}'''
new = '''    ok, why = health(crash_mark)
    tps = frames / wall if wall else 0.0
    dirty = ark_state(card) != ark_mark
    return {"tps": tps, "cpu": (c0 + c1) / 2.0,
            "ms_tick": 1000.0 * (c0 + c1) / 2.0 / tps if tps else 0.0,
            "healthy": ok, "why": why, "contaminated": dirty}'''
assert old in s
s = s.replace(old, new, 1)
s = s.replace('def window(tid, seconds, crash_mark):', 'def window(tid, seconds, crash_mark, card="genesis"):', 1)
s = s.replace('''    # запоминаем конец лога ДО запроса''', '''    ark_mark = ark_state(card)
    # запоминаем конец лога ДО запроса''', 1)
s = s.replace('window(tid, 240, crash_mark)', 'window(tid, 240, crash_mark, args.map.lower())')
s = s.replace('window(tid, 300, crash_mark)', 'window(tid, 300, crash_mark, args.map.lower())')

# перед каждым окном ждать конца сохранения
s = s.replace('    print("П0/П1: базовая линия", flush=True)',
              '    print("П0/П1: базовая линия (жду конца сохранения мира)", flush=True)\n'
              '    save_idle(args.map.lower())')
s = s.replace('    print("П2: overlaptrim=0 (оседание 180 с, окно 300 с)", flush=True)',
              '    print("П2: overlaptrim=0 (жду конца сохранения, оседание 180 с, окно 300 с)", flush=True)\n'
              '    save_idle(args.map.lower())')
s = s.replace('    print("П2: overlaptrim=2 (оседание 180 с, окно 300 с)", flush=True)',
              '    print("П2: overlaptrim=2 (жду конца сохранения, оседание 180 с, окно 300 с)", flush=True)\n'
              '    save_idle(args.map.lower())')

# в отчёт — флаг искажения
s = s.replace('''    print("   t/s %.2f | cpu %.3f | %.2f мс/тик | %s"
          % (res["p01"]["tps"], res["p01"]["cpu"], res["p01"]["ms_tick"], res["p01"]["why"]), flush=True)''',
'''    print("   t/s %.2f | cpu %.3f | %.2f мс/тик | %s | искажено сохранением: %s"
          % (res["p01"]["tps"], res["p01"]["cpu"], res["p01"]["ms_tick"], res["p01"]["why"],
             res["p01"].get("contaminated")), flush=True)''')
io.open(p, "w", encoding="utf-8", newline="").write(s)
import ast; ast.parse(s)
print("слот: учёт сохранений мира (save_idle + флаг contaminated)")

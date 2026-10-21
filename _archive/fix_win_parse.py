import io

P = r"C:\Dev\_research\slot_measure.py"
s = io.open(P, encoding="utf-8", newline="").read().replace("\r\n", "\n")

OLD = '''    for ln in reversed(fresh):
        if "perf окно" in ln:
            for tok in ln.split():
                if tok.startswith("frames="):
                    frames = int(tok.split("=")[1])
                if tok.startswith("wall="):
                    wall = float(tok.split("=")[1].rstrip("s"))
            break'''

NEW = '''    # Плагин пишет итог окна строкой вида
    #   window итог: t/s=50 cpu=1390s ms/tick=137 frame_ms=19 busy=695% save=idle VALID
    # (метка "perf окно" - устаревшая, из-за неё парсер молчал и т/с было 0).
    # Поля cpu=/ms/tick=/busy= в этой строке НЕДОСТОВЕРНЫ: базовый отсчёт
    # процессора не вычитается. Достоверны t/s=, frame_ms=, save=, VALID/CONTAMINATED.
    frame_ms = 0.0
    plugin_tps = 0.0
    saved = ""
    valid = ""
    for ln in reversed(fresh):
        if "window" in ln and "t/s=" in ln:
            for tok in ln.split():
                if tok.startswith("t/s="):
                    plugin_tps = float(tok[4:])
                elif tok.startswith("frame_ms="):
                    frame_ms = float(tok[9:])
                elif tok.startswith("save="):
                    saved = tok[5:]
                elif tok in ("VALID", "CONTAMINATED"):
                    valid = tok
            if plugin_tps <= 0 and frames and wall:
                plugin_tps = frames / wall
            break'''

assert OLD in s, "не нашёл старый блок разбора"
s = s.replace(OLD, NEW, 1)

OLD_RET = '''    tps = frames / wall if wall else 0.0
    dirty = ark_state(card) != ark_mark
    return {"tps": tps, "cpu": (c0 + c1) / 2.0,
            "ms_tick": 1000.0 * (c0 + c1) / 2.0 / tps if tps else 0.0,
            "healthy": ok, "why": why, "contaminated": dirty}'''

NEW_RET = '''    tps = plugin_tps or (frames / wall if wall else 0.0)
    cpu = (c0 + c1) / 2.0
    dirty = ark_state(card) != ark_mark
    if valid == "CONTAMINATED":
        dirty = True
    return {"tps": tps, "cpu": cpu,
            "ms_tick": 1000.0 * cpu / tps if tps else 0.0,
            "frame_ms": frame_ms, "save": saved, "verdict": valid,
            "healthy": ok, "why": why, "contaminated": dirty,
            # кросс-чек: кадр плагина против внешнего счёта CPU/тик
            "cross_diff_pct": (abs(1000.0 * cpu / tps - frame_ms) / frame_ms * 100.0)
                               if (tps and frame_ms) else None}'''

assert OLD_RET in s, "не нашёл старый возврат"
s = s.replace(OLD_RET, NEW_RET, 1)

io.open(P, "w", encoding="utf-8", newline="\r\n").write(s)
print("slot_measure: разбор строки окна исправлен, добавлен кросс-чек")
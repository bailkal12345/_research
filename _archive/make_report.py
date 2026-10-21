# -*- coding: utf-8 -*-
"""
Генератор REPORT-<карта>.md по результатам слота (Агент-4, doit.txt §6).
Только цифры. Ответы на три вопроса раздела 2 — в начале файла.

    python make_report.py <карта>
"""
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def fmt(v, nd=2, dash="н/д"):
    if v is None:
        return dash
    try:
        return ("%." + str(nd) + "f") % float(v)
    except Exception:
        return str(v)


def main():
    if len(sys.argv) < 2:
        print("нужно указать карту")
        return 1
    card = sys.argv[1]
    src = os.path.join(HERE, "slot-%s.json" % card)
    if not os.path.exists(src):
        print("нет данных слота:", src)
        return 2
    with open(src, encoding="utf-8") as f:
        r = json.load(f)

    if r.get("error"):
        print("слот пропущен:", r["error"])
        return 3

    p01 = r.get("p01", {})
    off = r.get("p2_off", {})
    on = r.get("p2_on", {})
    p3 = r.get("p3_ms", [])

    lines = []
    A = lines.append
    A("# REPORT-%s" % card)
    A("")
    A("Слот: %s → %s. Тик GameThread (tid %s)."
      % (r.get("started", "?"), r.get("finished", "?"), r.get("tid", "?")))
    A("NetServerMaxTickRate: штатное (0), фактический t/s П0/П1: **%s**."
      % fmt(p01.get("tps")))
    A("")
    A("## Ответы на вопросы вахты")
    A("")
    A("**1. Сколько стоит реальный сейв без игроков.**")
    A("   t/s = %s, CPU GameThread = %s s/s, **%s мс CPU на тик**."
      % (fmt(p01.get("tps")), fmt(p01.get("cpu"), 3), fmt(p01.get("ms_tick"))))
    A("   Топ-символы — в разделе «Профиль» ниже.")
    A("")
    if off and on:
        delta = r.get("p2_delta_pct", 0.0)
        A("**2. Жрёт ли большие базы GameThread через O(n²) overlap.**")
        A("   overlaptrim=0: %s мс/тик (%s т/с) · overlaptrim=2: %s мс/тик (%s т/с)."
          % (fmt(off.get("ms_tick")), fmt(off.get("tps")),
             fmt(on.get("ms_tick")), fmt(on.get("tps"))))
        A("   **Дельта: %+.1f%% времени на тик.**" % (-delta))
        A("")
    if p3:
        A("**3. Сколько стоит фриз SaveWorld.**")
        A("   Прогоны: %s мс. Порог ТЗ (500 мс): %s."
          % (" / ".join(fmt(v, 0) for v in p3),
             "ПРЕВЫШЕН — ТЗ в бэклог" if max(p3) > 500 else "не превышен"))
        A("")
    A("## П0/П1 — базовая линия (прод-конфигурация)")
    A("")
    A("| Метрика | Значение |")
    A("|---|---|")
    A("| тиков/с | %s |" % fmt(p01.get("tps")))
    A("| CPU GameThread, s/s | %s |" % fmt(p01.get("cpu"), 3))
    A("| мс CPU на тик | %s |" % fmt(p01.get("ms_tick")))
    A("| CPU на прогреве, s/s | %s |" % fmt(r.get("cpu_warm"), 3))
    A("| профиль | %s |" % r.get("profile", "—"))
    A("")
    if r.get("top20"):
        A("### Профиль: топ-20 (self time, без простоев)")
        A("")
        A("| Доля | Символ |")
        A("|---|---|")
        for share, name in r["top20"]:
            A("| %s | `%s` |" % (share, name.strip()))
        A("")
    if r.get("censuses"):
        A("### Переписи")
        A("")
        for c in r["censuses"]:
            A("- %s" % c)
        A("")
    if off and on:
        A("## П2 — overlaptrim: A/B (окна 300 с после 180 с оседания)")
        A("")
        A("| Режим | мс CPU/тик | т/с | CPU, s/s |")
        A("|---|---|---|---|")
        A("| overlaptrim=0 | %s | %s | %s |" % (fmt(off.get("ms_tick")), fmt(off.get("tps")),
                                               fmt(off.get("cpu"), 3)))
        A("| overlaptrim=2 | %s | %s | %s |" % (fmt(on.get("ms_tick")), fmt(on.get("tps")),
                                               fmt(on.get("cpu"), 3)))
        A("| **дельта** | **%+.1f%%** | | |" % (-r.get("p2_delta_pct", 0.0)))
        A("")
    if p3:
        A("## П3 — SaveWorld")
        A("")
        A("| Прогон | фриз, мс |")
        A("|---|---|")
        for i, v in enumerate(p3, 1):
            A("| %d | %s |" % (i, fmt(v, 0)))
        A("")

    out = os.path.join(HERE, "REPORT-%s.md" % card)
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("записан", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
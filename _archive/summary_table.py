# -*- coding: utf-8 -*-
"""
Сводная таблица вахты по картам (Агент-4, doit.txt §6.2).

    python summary_table.py
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# эталоны из базы знаний (doit.txt §7) для сверки
REF = {
    "cpu_empty": -79.0,      # −79% CPU на пустом мире
    "cpu_player": -77.7,     # −77.7% с игроками
    "clamp_gain": 1.9,       # ×1.9 от снятия клампа
    "ceiling": "200-290 т/с",
}


def main():
    rows = []
    for f in sorted(glob.glob(os.path.join(HERE, "slot-*.json"))):
        card = os.path.basename(f)[5:-5]
        try:
            with open(f, encoding="utf-8") as fh:
                r = json.load(fh)
        except Exception:
            continue
        if r.get("error"):
            rows.append((card, r["error"], "—", "—", "—", "—"))
            continue
        p01 = r.get("p01", {})
        off = r.get("p2_off", {})
        on = r.get("p2_on", {})
        p3 = r.get("p3_ms", [])
        p3max = max(p3) if p3 else None
        delta = r.get("p2_delta_pct")
        rows.append((
            card,
            "ок",
            "%.2f" % p01.get("tps", 0),
            "%.2f" % p01.get("ms_tick", 0),
            ("%+.1f%%" % (-delta)) if delta is not None else "—",
            ("%.0f" % p3max) if p3max is not None else "—",
        ))

    out = []
    out.append("# Сводная таблица вахты prod-сейвов")
    out.append("")
    out.append("| Карта | Слот | t/s (П0/П1) | мс CPU/тик (П0/П1) | дельта overlaptrim (П2) | фриз SaveWorld, мс (П3) |")
    out.append("|---|---|---|---|---|---|")
    for r in rows:
        out.append("| %s | %s | %s | %s | %s | %s |" % r)
    if not rows:
        out.append("| — | нет завершённых слотов | — | — | — | — |")
    out.append("")
    out.append("## Эталоны для сверки")
    out.append("")
    out.append("| Величина | Значение |")
    out.append("|---|---|")
    out.append("| CPU, пустой мир | %s%% |" % REF["cpu_empty"])
    out.append("| CPU, с игроками | %s%% |" % REF["cpu_player"])
    out.append("| Снятие клампа | ×%s |" % REF["clamp_gain"])
    out.append("| Потолок | %s |" % REF["ceiling"])
    out.append("")
    path = os.path.join(HERE, "SUMMARY.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out))
    print("записан", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
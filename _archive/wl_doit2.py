import io, datetime
add = """
## {ts} ВАХТА 2 (doit2.txt) — СТАРТ

Прочитано: worklog.md, REPORT-Genesis.md, REPORT-TheIsland.md, REPORT-Fjordur.md, SUMMARY.md.

Принятые из п.0 факты (зафиксированы как есть):
  * пустой сервер на 3 картах: 9.99 т/с при 9-10 мс CPU/тик, лимит - пейсинг;
  * базовая цифра с игроком (старые прогоны, Genesis): 24.4 мс/тик, цель 60 т/с = <=16.6 мс/тик;
  * overlaptrim: Genesis -59.0%, Fjordur -39.0%, TheIsland -9.1%;
  * фриз SaveWorld 3.9-4.3 с, порог ТЗ 500 мс превышен в 7.5-8.7 раза;
  * АНОМАЛИЯ ПРИНЯТА: переписи Genesis/TheIsland сняты в восстановленном состоянии
    (после overlapall 0; повторный overlaptrim 2 живые компоненты не перечищает),
    Fjordur - в деплой-состоянии. П0/П1 между картами несравнимы.

Протокол откатов: каждый слот начинается с деплоя из c:/saves через deploy_map.py.
Размер+хеш .ark фиксируются до и после каждого изменения состояния.
"""
add = add.replace("{ts}", datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
io.open(r"C:\Dev\_research\worklog.md", "a", encoding="utf-8").write(add)
print("worklog: старт вахты 2")

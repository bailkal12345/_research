import io, time, datetime
p = r"C:\Dev\_research\worklog.md"
s = io.open(p, encoding="utf-8").read()
add = """
## {ts} ВАХТА prod-сейвов: старт (директива doit.txt)

Начальное состояние сервера зафиксировано ДО первого прогона (п.4 директивы):
  - се��вер: ShooterGameServer.exe, SavedArks = Genesis.ark (102.7 МБ) — развёрнут
    предыдущим прогоном deploy_map.py (23:23), повторный деплой не требуется;
  - RCON: 192.168.8.218:32330 (проверен, отвечает), порт 27020 в bench-запуске
    deploy_map.py не используется этой вахтой;
  - fixclamp: авто-подъём зажима при загрузке плагина (П12) -> будет выключен
    перед П0/П1 согласно прод-конфигу;
  - NetServerMaxTickRate: 0 (штатно, 30 т/с);
  - пять оптимизаций (fncache/iscache/cachename/nochart/overlaptrim=2): вкл;
  - запрещённые команды не вызываются; выгрузка плагина не производится.

Очередь сейвов (автопоиск c:/saves): Genesis -> TheIsland -> Fjordur.
Слот 1 = Genesis (уже развёрнут, старт без деплоя).
""".replace("{ts}", datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
io.open(p, "a", encoding="utf-8").write(add)
print("worklog дописан")

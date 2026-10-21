import io, datetime
p = r"C:\Dev\_research\worklog.md"
add = """
## {ts} Слот 1 (Genesis): авария и разбор краша

Симптом: П0/П1 вернул t/s 0.00, cpu 0.000 — измерять было нечего.

Крашстак Saved/Logs/10.17-23.39.18.crashstack (5200 байт):
  LowLevelFatalError [ShooterGameMode.cpp:2847]
  "Can't load world save file, please replace it with the latest backup."
  Стек: FEngineLoop::Tick -> UGameEngine::Tick -> UEngine::TickWorldTravel ->
        UEngine::Browse -> UEngine::LoadMap -> UWorld::InitializeActorsForPlay ->
        AShooterGameMode::InitGame -> AShooterGameMode::LoadWorld (строка 2849)
  VERSION: 361.7, Last Remote Function NetDeactivate.

Вывод: это НЕ порча сейва, а попытка смены карты (TickWorldTravel) на сейв,
которого нет в SavedArks. Фатальная ошибка вызвала RequestExit(1) — поэтому
в предыдущем игровом логе видно "FPlatformMisc::RequestExit(1)" и закрытие лога
в 23:39:24, через 6 секунд после краша.

Состояние сейва ПРОВЕРЕНО:
  * SavedArks/genesis.ark = 102.72 МБ, mtime 20.11.2025 — исходный, не переписывался;
  * текущий процесс (pid 17488, ручной запуск RunServer.cmd) загрузил этот сейв
    успешно: в логе присутствует подключение игрока, Day 15, 625 существ;
  * значит восстановление из архива НЕ ТРЕБУЕТСЯ.

Дополнительно: имя файла на диске в нижнем регистре (genesis.ark). deploy_map.py
проверяет "Genesis.ark" — на Windows это тот же файл, деплой корректен.

Действия: слот 1 зафиксирован как ПРОПУЩЕН (краш на этапе прогона),
продолжаю на текущем процессе после стабилизации. Архив не трогаю.
""".replace("{ts}", datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
io.open(p, "a", encoding="utf-8").write(add)
print("worklog дописан")

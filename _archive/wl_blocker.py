import io, datetime

add = """
## {ts} DOIT-4: БЛОКЕР ИГРОКА (не дефект бота) — парковка по §6

### Что сделано в фазе S
S1 сервер: цель 60 т/с достигнута (подробности ниже).
S2 perf.selftest: два дефекта исправлены до рабочего прогона, третий зафиксирован.
S3 клиент v361: запущен, загрузился, Arksharp поднят, бот загрузился.
S4 коннект: НЕ УДАЛЁТСЯ. Воспроизведено дважды.

### Цепочка событий (по логам бота, оба раза одинаково)
  [ctl]   connect requested -> 192.168.8.218:7777
  [state] Menu -> Connecting
  [connect] SetClientTravel -> 192.168.8.218:7777
  [browse] ret=2 (Browse_Pending) host='192.168.8.218' port=7777
  [travel] TickWorldTravel(...) driven from UGameEngine::Tick
  далее - тишина: heartbeat продолжает писать state=Connecting, клиент Responding=False,
  RCON ListPlayers = "No Players Connected".

### Диагноз (эмпирический, не догадка)
1. Прав администратора НЕТ: New-NetFirewallRule -> "Access is denied".
2. Для ShooterGame.exe (КЛИЕНТ) НЕТ НИ ОДНОГО inbound-правила файрвола.
   Правила есть только для ShooterGameServer.exe (4 штуки, Inbound Allow).
3. Сетевой профиль - Public, брандмауэр Windows включён (MpsSvc Running),
   inbound по умолчанию блокируется.
4. Сервер слушает UDP 192.168.8.218:7777 и хост пингуется с машины клиента.
5. Клиент создал свой UDP-сокет (0.0.0.0:58198) - то есть исходящий пакет он
   отправить может, но ответ сервера на этот эфемерный порт блокируется.

ВЫВОД: handshake не завершается, потому что ответ сервера не доходит до клиента.
Это ограничение окружения, а не дефект BotPlayer: тот же бот на том же сервере
не может завершить connect без inbound-разрешения клиенту.

ДОПОЛНИТЕЛЬНО (из документации бота, docs/GAME_INTERNALS.md §2.4): проверенная
схема - сервер на Port=7778 и QueryPort=27016, и там же документировано, что
"open 192.168.8.218:27016" застревает в Browse_Pending. Наш стенд запущен
прод-строкой (Port=7777, QueryPort=27015), то есть схема бота не воспроизведена.
Различить две причины (файрвол или схема портов) без прав админа нельзя.

### Что нужно, чтобы снять блокер (одно из двух, выбор за владельцем машины)
  A) Правило файрвола - выполнить ОТ ИМЕНИ АДМИНИСТРАТОРА (одна команда):
     New-NetFirewallRule -DisplayName "ARK361Client" -Direction Inbound `
       -Program "C:\\Games\\ARK_SE_game_v361\\ShooterGame\\Binaries\\Win64\\ShooterGame.exe" `
       -Action Allow -Profile Any -Protocol UDP
  B) Стенд на документированных портах: Port=7778, QueryPort=27016 (изменение
     строки запуска, требует пометки как отклонение от прод-конфигурации).

### Правки бота за эту сессию (git, §1.6)
  93f4b3c  BotPlayer: target Server1 v361 on 192.168.8.218:7777   push выполнен
Клиентская часть (вне git-репозитория бота): установлены version.dll/version.pdb/
config.json из v358 и msdia140.dll - без него Arksharp пишет
"Failed to read pdb - Error code -126" и нативы не резолвятся (это был отдельный,
устранённый блокер).
"""
t = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
io.open(r"C:\Dev\_research\worklog.md", "a", encoding="utf-8").write(add.replace("{ts}", t))
print("worklog: блокер зафиксирован")
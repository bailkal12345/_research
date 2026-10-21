import io, datetime

add = """
## {ts} DOIT-4: починка бота для v361 (коммиты 46146fb, 6c6a188)

Задача: автоматический вход бота в сервер на TheIsland (192.168.8.218:7777),
который руками подтверждён как рабочий.

### Что сделано в коде (оба коммита запушены)
1. connectViaConsole (по умолчанию true): подключение через консольную команду
   `open <addr>` вызовом AShooterPlayerController::ConsoleCommand (SDK-сигнатура
   ConsoleCommand(result, cmd, bWriteToLog) проверена в ARK-Game-API). Это тот же
   путь, что использует сервер-браузер игры. SetClientTravel оставлен как запасной
   (connectViaConsole=false).
2. Диагностика, потому что старая поломка была молчаливой:
   - status: connectAttempts, connectBounces, connectPendingS, connectMethod, browseRet
   - смена world во время Connecting теперь считается и логируется (connectBounces)
   - раз в 60 с лог "still Pending after N s" с попытками/отскоками/browse
   - хук Browse пишет host и ret отдельной строкой
3. Команда ctx: сканирует FWorldContext на FURL-подобные поля (Valid@0x58,
   Port@0x20, Host@0x10, Map@0x28, размер 96 - раскладка идентична v358 и
   подтверждена в Ghidra по v361). Показывает, какой URL реально принял движок.

### Что установлено экспериментально
- open <ip>:<port>            -> FURL валиден (valid=1), но Browse_Pending навсегда,
                                 клиент виснет (TCP перестаёт отвечать).
- open steam:<steamid>:<port> -> Browse_Failure, err='Invalid URL' (движок не берёт).
- SetClientTravel             -> то же Pending, что и open.
Вывод: офсеты, SteamID-формат и сеть исправны - не хватает того, что делает
рукописный вход из сервер-браузера.

### Открытый вопрос (нужен ручной вход)
Чтобы узнать рабочий URL, нужен успешный ручной вход: после него ctx покажет
FWorldContext::LastURL - тот самый URL, по которому соединение установилось.
"""
t = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
io.open(r"C:\Dev\_research\worklog.md", "a", encoding="utf-8").write(add.replace("{ts}", t))
print("worklog: починка бота зафиксирована")
import io, datetime

add = """
## {ts} DOIT-4: ПОЧИНКА БОТА - итог (9 коммитов)

### Задача
Автоматический вход бота в сервер 192.168.8.218:7777 (карта TheIsland), который
руками подтверждён как рабочий.

### Сделано и запушено (репозиторий бота)
  46146fb консольный путь `open` + диагностика подключения
  6c6a188 команда ctx - разбор FWorldContext
  66e10d2 путь карты в travel URL
  6f6bd5d сборка URL как unreal://host:port/map
  6f48641 сборка FURL вручную + прямой вызов UEngine::Browse
  fb27110 не уничтожать FURL (use-after-free)
  2fe4348 Pending считать начатой попыткой (анти-спам)
  7521a8b ctx печатает все поля FURL, включая Op[]
  93b5f59 заполнение Op[] опциями game= и ModId
  2b337de сборка Op[] вручную вместо TArray::Add
  e74c179 печать Op[] до вызова Browse

### Что установлено точно (Ghidra по v361_ShooterGame.exe)
- Офсеты бота верны: FURL (96 б, Protocol 0x00 / Host 0x10 / Port 0x20 /
  Map 0x28 / Op 0x38 / Portal 0x48 / Valid 0x58) идентична v358; FWorldContext
  World=0x260, TravelURL=0xB8 (подтверждено инструкциями MOV/LEA).
- Разбор URL движком принимает ТОЛЬКО голый "ip:port". Всё остальное отвергается:
    192.168.8.218:7777                                    valid=1, Pending
    192.168.8.218:7777/Game/Maps/...TheIsland             Invalid URL
    unreal://192.168.8.218:7777/Game/Maps/...TheIsland    Invalid URL
    steam:90295185431854102:7777                          Invalid URL
- Рабочее соединение (ручной вход) держит в FWorldContext:
    proto=unreal host=192.168.8.218 port=7777 valid=1
    map=/Game/Maps/TheIslandSubMaps/TheIsland
    Op[0]=ModId=0
    Op[1]=game=/Game/PrimalEarth/CoreBlueprints/TestGameMode.TestGameMode_C
  Эти поля бот теперь воспроизводит точно - проверено логом до вызова Browse.

### Найдено и исправлено два настоящих бага бота
1. use-after-free: FURL, отданная Browse, освобождалась сразу после вызова,
   а UPendingNetGame продолжает её читать - клиент падал. Теперь "протекает"
   намеренно.
2. Спам переподключений: Browse=2 (Pending) трактовался как неудача, бот делал
   1384 попытки за секунды - ровно тот паттерн, который Hooks.cpp называет
   путём к __fastfail в ucrtbase.

### Итог
FURL, с которым бот зовёт Browse, теперь совпадает с рабочим соединением
поле в поле, движок его принимает (valid=1) и уходит в Pending - но клиент
печатает таймаут. Значит различие НЕ в URL: сервер-браузер делает что-то ДО
Browse, чего бот не повторяет (создание net driver / сессия Steam / серверный
запрос). Это отдельная задача - разобрать путь Join в браузере.

### Что работает уже сейчас
Ручной вход + бот = полностью рабочая сессия: бот видит state=Active, pawn,
координаты, дистанцию от спавна, инвентарь, и выполняет move/goto/set.
То есть для измерительного слота (игрок в мире, стоит) контур готов; не
автоматизирован только сам вход.
"""
t = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
io.open(r"C:\Dev\_research\worklog.md", "a", encoding="utf-8").write(add.replace("{ts}", t))
print("worklog: итог починки бота зафиксирован")
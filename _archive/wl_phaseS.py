import io, datetime

add = """
## {ts} DOIT-4 ФАЗА S — дым: серверная часть (окна не снимались)

### S1 сервер: целевая конфигурация
Деплой Genesis из архива (deploy_map.py), прод-строка. Ключевая поправка:
NetServerMaxTickRate=60 прописана в GameUserSettings.ini (файл в UTF-16).
СТРОГА НЕ ПОДХВАТИЛАСЬ - при старте движок держит 30, поэтому по §2 применено
runtime "TickProf.maxfs 60" ПОСЛЕ config (иначе config возвращает maxfps 0).
Отклонение отмечено: цель воспроизводима только через runtime-команду.
Проверка: fixclamp 0, пять оптимизаций вкл, bAllowConcurrentTicks=0.
overlaptrim 2 -> отключено 8722 компонентов, освобождено 71670 записей.

ГЕЙТ "мир загружен" пройден (18:23): т/с 59-60, кадр 16 мс, мс/тик 7-9, busy 43-54%.
Повторная проверка 19:01: т/с 53-56, кадр 17-18 мс, мс/тик 6-9, busy 35-53%.
Транзиент в 18:55 (т/с 30, busy 98-100%, мс/тик 31-34) - проход автосейва, не загрузка.

### S2 perf.selftest - ПЕРВЫЙ прогон: ДВА ДЕФЕКТА НАЙДЕНЫ ДО РАБОЧЕГО ПРОГОНА

Дефект 1 (критичный, грозили падением сервера): selftest звал RCON-обработчики
с nullptr-пакетом (CmdOverlapAll/CmdOverlapTrim/CmdOverlaps), а ArgInt делает
packet->Body -> разыменование NULL. Исправлено: тела логики вынесены в
DoOverlapAll(bool) / DoOverlapTrim(int) / DoOverlapsCensus(int), обработчики
стали тонкими обёртками, selftest зовёт безопасные функции.

Дефект 2 (общий, существовал и до этой сессии): ArgInt(packet, N) - это
"последний токен команды, иначе N", а НЕ "N-й аргумент". Из-за этого:
  - TickProf.overlaptrim 7 давал порог 2 (значение по умолчанию), а не 7;
  - "perf.selftest 20 120 0" игнорировал все три аргумента.
Добавлены ArgTokens/ArgN(индекс)/ArgLast. Проверено на стенде:
"overlaptrim 7" -> в логе "порог=7"; "selftest 18 120 0" -> "бюджет 18 мин,
окно 120 с, профиль нет".

Дефект 3 (НЕ чинил, по §S2 фиксирую и иду ручным протоколом): selftest зависает
в фазе ST_WAIT_WORLD. Условие - g_game_tid.load() ненулевое, а значение в лог
попало ("game thread tid=16400"), то есть проверка не проходит. Прогон от 18:48:27
не выдал ни одной фазы за 8 минут. Слот не срываю - работаю ручным протоколом.

### Бот BotPlayer - ОШИБКА БЫЛА В МОЁЙ РЕШЕТКЕ, ИСПРАВЛЕНА
Изначально я принял бота за серверный плагин (README указывает путь
ArkApi\\Plugins) и развернул его НА СЕРВЕРЕ. Это неверно: BotPlayer - клиентский
плагин, он хукает AShooterPlayerController::ClientShowSpawnUI, UEngine::Browse,
UGameEngine::ick и резолвит нативы из ShooterGame.pdb (клиентский PDB).
Развернул его на сервере - убрал.
Правильно: C:\\Games\\ARK_SE_game_v361\\...\\Win64\\ArkApi\\Plugins\\BotPlayer\\
(раскладка плоская, как в рабочей v358). Хеш BotPlayer.dll совпадает с рабочим
в v358: 6826DA28147CC8EA.
Загрузчик Arksharp в v361 отсутствовал (есть только version.dll_ - нет, файла
нет вовсе). Взял из v358 по указанию: version.dll_, version.pdb, config.json.
Установил как version.dll + version.pdb + config.json.

Правка бота (git, §1.6):
  коммит 93f4b3c "BotPlayer: target Server1 v361 on 192.168.8.218:7777"
  (в конфиге стояли 27016 и fallback 7778; стенд слушает 7777)
  push выполнен: 2cbb265..93f4b3c HEAD -> main, без force.

### S3 клиент запущен
ShooterGame.exe v361, -windowed -ResX=1280 -ResY=720 -NoSplash -log.
Загрузка клиента идёт, окон измерения по §1.5 не снимаются.
"""
t = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
io.open(r"C:\Dev\_research\worklog.md", "a", encoding="utf-8").write(add.replace("{ts}", t))
print("worklog: фаза S зафиксирована")
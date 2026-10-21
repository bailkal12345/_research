import io, datetime
p = r"C:\Dev\_research\worklog.md"
add = """
## {ts} ГИПОТЕЗА ПРО Steam ОПРОВЕРГНУТА; НАЙДЕНА НАСТОЯЩАЯ ПРИЧИНА ЗАМОРОЗКИ

Проверка гипотезы "-nossteamclient": флаг добавлен в строку запуска, сервер
перезапущен на Genesis (pid 5144) — заморозка повторилась (CPU 0.002/0.003
на 00:07:11 и 00:07:47). В логе по-прежнему "SteamSocketsOpenSource:
gethostname failed ()". ВЫВОД: -nossteamclient не влияет на инициализацию
SteamSockets в v361, гипотеза неверна. Детектор заморозки при этом отработал
правильно: подтвердил за 3 минуты вместо 15 и снял процесс.

Дополнительно найдены две ошибки инструментов:
  1. deploy_map.py вызывал 7z как "7z" — 7-Zip не прописан в PATH,
     поэтому ВСЕ .7z-архивы (TheIsland, Fjordur) падали с
     FileNotFoundError [WinError 2]. Genesis.zip распаковывался штатным
     zipfile, поэтому первая карта проходила, а остальные нет.
     Исправлено: SEVENZIP = абсолютный путь к 7z.exe.
  2. watch_shift.py читал вывод subprocess без явной кодировки -> cp1252 ->
     UnicodeDecodeError и потеря русских строк в логе. Исправлено.

Проверка гипотезы "нехватка ресурсов": диск C: свободно 104.84 ГБ, зомби-процессов
нет, память 5.4 ГБ из 64 ГБ. Не причина.

Проверка гипотезы "bench-строка запуска": deploy_map.py переведён на ПРОД-строку
из Saved/Config/WindowsServer/RunServer.cmd (MultiHome/Port/QueryPort/MaxPlayers=70
+ полный набор флагов, без SessionName/RCONEnabled/RCONPort в аргументах карты;
RCON берётся из GameUserSettings.ini: RCONEnabled=True, RCONPort=27020).
Результат: сервер поднялся с первой попытки — 7 минут непрерывной загрузки
(CPU 0.76-0.97), 00:16:17 game thread tid=16912, 00:16:35 RCON отвечает,
"ГОТОВ: карта Genesis".

ВЫВОД: причина заморозки — bench-строка запуска, а не сейв, не Steam, не ресурсы.
Конкретный виновник внутри неё не выделен: отличаются сразу несколько параметров
(SessionName=Bench_..., RCONEnabled/RCONPort в аргументах карты, MaxPlayers=10
вместо 70, отсутствие -game/-forcerespawndinos/-usestore и других флагов).
Дальнейшее сужение виновника не входило в вахту — важно, что прод-строка работает.
Отдельно отмечено: Genesis_AntiCorruptionBackup.bak создаётся в момент
заморозки (00:06:46), то есть замирание приходится на финал загрузки сейва.

Гипотеза "два процесса сервера" остаётся актуальной для аварии 23:39
(TickWorldTravel -> Can't load world save file), но к заморозке отношения не имеет.
"""
add = add.replace("{ts}", datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
io.open(p, "a", encoding="utf-8").write(add)
print("worklog дописан")

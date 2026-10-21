import io, datetime
p = r"C:\Dev\_research\worklog.md"
add = """
## {ts} РАЗБОР АВАРИИ 2: заморозка на загрузке (не битый сейв)

Симптом: слот 1 (Genesis) снова без результата. Процесс 10736 жив, Responding=True,
32 потока, но суммарно 0.00 CPU; RCON слушал 27020 и не отвечал; в логе плагина
нет строки "game thread tid=" — первый тик UGameEngine::Tick так и не случился.

Диагностика:
  * Windows Application log — пусто (исключений ОС нет);
  * Saved/Logs/Dump-490729840.dmp (231 КБ, 23:54:50) разобран своим парсером
    dumpinfo.py: 29 потоков в дампе совпадают с живым процессом => дамп от него.
    ExceptionCode 0x00000001, ExceptionAddress 0x00007FF93B6F6D9A = KERNELBASE.dll+0xC6D9A
    (тот же адрес стоял первым в крашстаке 23:39:18 — это RaiseException);
  * из 113 модулей в дампе грузятся steam_api64.dll, steamclient64.dll,
    tier0_s64.dll, vstdlib_s64.dll, crashhandler64.dll из C:\\Program Files (x86)\\Steam,
    а также GameNetworkingSockets.dll;
  * в ShooterGame.log после InitWorld: "SteamSocketsOpenSource: gethostname failed ()"
    и "gethostbyname failed ()" — сети до Steam нет.

ВЫВОД: сейв ни при чём. Цепочка: deploy_map.py запускал сервер БЕЗ -nosteamclient ->
подсистема Steam цеплялась -> без сети крашхендлер Steam снимает дамп ->
процесс остаётся жив с нулевым CPU навсегда (заморозка). Именно поэтому слот
видел нули, а RCON не отвечал.

Измерение заморозки (freeze.py): доля CPU = 0.003 при норме >0.5.

Что сделано (правки инструментов, не поведение сервера):
  1. deploy_map.py: в строку запуска добавлен -nosteamclient (как в рабочем
     RunServer.cmd, который успешно поднимался 23:27-23:47 с игроком);
  2. deploy_map.py rcon_ready(): детектор заморозки — 2 подтверждения подряд
     по 20 с => процесс снимается и слот помечается пропуском (3 мин вместо 15);
  3. slot_measure.py wait_ready(): тот же детектор;
  4. slot_measure.py health(): заморозка проверяется ПЕРВОЙ, до RCON, потому что
     на замороженном сервере RCON молчит и выглядит как "не поднялся";
  5. dumpinfo.py — разбор минидампа MDMP без внешних зависимостей.

Проверка гипотезы: предыдущий успешный запуск 8140 делался той же строкой без
-nosteamclient и Steam тогда уступил — то есть поведение недетерминированное,
зависит от того, успел ли Steam-крашхендлер сработать. Поэтому флаг -nosteamclient
обязателен, а не желателен.

Состояние сейва: genesis.ark 102.72 МБ не тронут (бэкапы в SavedArks.prev на месте).
"""
add = add.replace("{ts}", datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
io.open(p, "a", encoding="utf-8").write(add)
print("worklog дописан")

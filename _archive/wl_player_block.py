import io, datetime

add = """
## {ts} DOIT-4: сессия с игроком - разбор блокера (окна не снимались)

### Итог коротко
Игрок в мир не входит. Клиент доходит до Browse_Pending, частично получает
PlayerController, затем мир выгружается и клиент возвращается в Connecting.
С добавлением Goldberg-эмулятора клиент перестал падать, но вход не появился.
Владелец стенда проверил то же самое БЕЗ бота - тот же результат, значит
проблема в клиенте/окружении, а не в BotPlayer.

### Что проверено по коду (Ghidra, v361_ShooterGame.exe)
Жесткие смещения BotPlayer перепроверены против 361 - ВСЕ СОВПАДАЮТ:
  FURL (96 б): Protocol 0x00, Host 0x10, Port 0x20, Map 0x28, Op 0x38,
               Portal 0x48, Valid 0x58  (раскладка Ghidra идентична;
               в UEngine::Browse видны CMP dword [RSI+0x58] и MOV [RSI+0x28])
  FWorldContext: World 0x260 (11 обращений [RSI+0x260] в TickWorldTravel),
               TravelURL 0xB8 (бот читает верный URL, длина 19-20 сходится)
Смещения не являются причиной.

### Что проверено по сети
Сервер слушает UDP 192.168.8.218:7777 и QueryPort 27015.
A2S на 27015 работает: отдаёт 0x41 GETCHALLENGE, затем A2S_PLAYER_RULES:
  P2PADDR = 90295185431854102   P2PPORT = 7777
  CUSTOMSERVERNAME = server1 - v361
  NETWORKING_i = 0   OWNINGID = 90295185431854102
Travel-URL по этому SteamID ("90295185431854102:7777") клиент НЕ ПРИНИМАЕТ:
FURL::Parse -> valid=0, UEngine::Browse -> Browse_Failure.
Клиент грузит GameNetworkingSockets + steamclient64, т.е. сеть Steam.

### Попытки адреса (все откачены коммитом 79e7286)
  сырой IP 7777            - handshake не идёт, PlayerState не приходит
  27016 (документ. дефолт) - на стенде никто не слушает
  QueryPort 27015 + длинный failover - тоже Pending
  SteamID как host          - Browse_Failure

### Правки бота (git, все запушены)
  93f4b3c адрес стенда 192.168.8.218:7777
  f1c8011 двухступенчатый коннект QueryPort -> игровой порт
  8ee20b3 autoConnect + autoSpawn (документированный автономный цикл)
  78f4144 прямой коннект к игровому порту, отказник выключен
  35c9c9a travel по SteamID64
  7f9701b возврат на QueryPort с длинным отказником
  79e7286 ОТКАТ BotPlayer.json к состоянию до сессии
Откат сделан по требованию владельца: файл вернулся к 27016/7778,
autoConnect/autoSpawn выключены. Репозиторий чист от экспериментов.

### Отдельные дефекты, найденные попутно (не чинились - слот)
1. TickProf.perf.selftest в фазе ST_AB_A_WINDOW уходит в горячий цикл:
   фаза ставится прямым g_st.store(...) без сброса метки времени, условие
   выполняется каждый кадр. За минуту - 11 МБ лога. Исправление = сброс
   метки при смене фазы (по §S2 в слоте не чинится).
2. ArgInt(packet, N) означает "последний токен, иначе N", а не "N-й аргумент".
   Из-за этого TickProf.overlaptrim 7 давал порог 2. Исправлено (ArgN/ArgLast).
3. selftest звал RCON-обработчики с nullptr-пакетом -> разыменование NULL.
   Исправлено: тела вынесены в DoOverlapAll/DoOverlapTrim/DoOverlapsCensus.

### Goldberg-эмулятор (установлен по требованию владельца)
Источник: github.com/Detanup01/gbe_fork, релиз release-2026_09_27.
Важная деталь: игра грузит Steam НЕ из корня клиента, а из бандла
  Engine\\Binaries\\ThirdParty\\Steamworks\\Steamv132\\Win64
и тянет steamclient64.dll из C:\\Program Files (x86)\\Steam.
Поэтому эмулятор поставлен в Steamworks-каталог, а steam_settings - рядом
с DLL (эмулятор ищет её относительно собственного пути).
  steam_api64.dll   22 583 720 байт (эмулятор) вместо 208 296
  steamclient64.dll    111 016 байт (эмулятор)
  steam_settings/configs.app.ini: [app::dlcs] unlock_all=1  (все DLC открыты)
  steam_settings/configs.main.ini: disable_networking=0, enable_steam_preowned_ids=1
  steam_settings/steam_appid.txt = 346110
  configs.user.ini: account_name=bench, account_steamid=76561197960287930
Бэкапы оригиналов: C:\\Dev\\_research\\steam_backup\\ (steamclient64.dll,
sw_steam_api64.dll). Откат = вернуть DLL и удалить steam_settings.
Сценарий установки: install_goldberg.ps1 + install_goldberg2.ps1.

### Проверенные версии адреса и их результат
  сырой IP:port   -> handshake не завершается, PlayerState нет
  QueryPort       -> A2S проходит, но клиент всё равно Pending
  SteamID64       -> URL невалиден

### Состояние стенда
Слот B0 не выполнен: ни одного измерительного окна с игроком не снято.
Правило §6 о парковке применяется. Профиль не снимался (после профиля
измерений не делаем).
"""
t = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
io.open(r"C:\Dev\_research\worklog.md", "a", encoding="utf-8").write(add.replace("{ts}", t))
print("worklog: разбор блокера зафиксирован")
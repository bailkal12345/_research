import io
import json
import re

P = r"C:\Dev\ark-bot-research\BotPlayer\Configs\BotPlayer.json"
s = io.open(P, encoding="utf-8").read()

# SteamID как хост не принимается: FURL::Parse возвращает valid=0 и
# UEngine::Browse отдаёт ret=1 (Browse_Failure). Клиент не умеет адресовать
# сервер напрямую по SteamID64 в travel URL.
#
# Рабочая схема - QueryPort (это и есть исходная схема бота): клиент сам
# делает A2S-обмен и берёт P2PADDR/P2PPORT из ответа сервера.
# Критично: не рвать этот обмен на 45-й секунде. connectFailoverSeconds
# поднят до 1200 с, потому что Hooks.cpp документирует повторный
# SetClientTravel при незавершённом Browse_Pending как путь к __fastfail.
s = re.sub(r'"serverAddress": "[^"]*"', '"serverAddress": "192.168.8.218:27015"', s)
s = re.sub(r'"serverAddressFallback": "[^"]*"', '"serverAddressFallback": "192.168.8.218:27015"', s)
s = re.sub(r'"connectFailoverSeconds": [0-9.]+', '"connectFailoverSeconds": 1200.0', s)

io.open(P, "w", encoding="utf-8", newline="\n").write(s)
cfg = json.loads(io.open(P, encoding="utf-8").read())
for k in ("autoConnect", "autoSpawn", "serverAddress", "serverAddressFallback",
          "connectDelaySeconds", "connectFailoverSeconds", "connectHardRetrySeconds"):
    print("%-24s = %s" % (k, cfg[k]))
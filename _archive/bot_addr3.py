import io
import json
import re

P = r"C:\Dev\ark-bot-research\BotPlayer\Configs\BotPlayer.json"
s = io.open(P, encoding="utf-8").read()

# A2S_PLAYER_RULES на QueryPort 27015 отдаёт:
#   P2PADDR = 90295185431854102   (SteamID64 сервера)
#   P2PPORT = 7777
#   CUSTOMSERVERNAME = server1 - v361
# Сервер работает через SteamSockets (GameNetworkingSockets + steamclient64
# загружены и в клиенте), поэтому адрес для SetClientTravel должен быть
# SteamID64:port, а не сырой IP: сырой IP клиент резолвит как обычный
# UDP-хост, handshake не завершается и PlayerState не приходит.
# Отказник поднят до 1200 с: перевызов SetClientTravel при незавершённом
# Browse_Pending документирован в Hooks.cpp как путь к __fastfail.
STEAMID = "90295185431854102"

s = re.sub(r'"serverAddress": "[^"]*"', '"serverAddress": "%s:7777"' % STEAMID, s)
s = re.sub(r'"serverAddressFallback": "[^"]*"', '"serverAddressFallback": "%s:7777"' % STEAMID, s)
s = re.sub(r'"connectFailoverSeconds": [0-9.]+', '"connectFailoverSeconds": 1200.0', s)

io.open(P, "w", encoding="utf-8", newline="\n").write(s)
cfg = json.loads(io.open(P, encoding="utf-8").read())
for k in ("autoConnect", "autoSpawn", "serverAddress", "serverAddressFallback",
          "connectDelaySeconds", "connectFailoverSeconds", "connectRetrySeconds",
          "connectHardRetrySeconds"):
    print("%-24s = %s" % (k, cfg[k]))
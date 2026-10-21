import io
import json
import re

P = r"C:\Dev\ark-bot-research\BotPlayer\Configs\BotPlayer.json"
s = io.open(P, encoding="utf-8").read()

# Отказник на 45-й секунде перевызывает SetClientTravel при незавершённом
# Browse_Pending. Hooks.cpp документирует ровно этот сценарий как источник
# __fastfail в ucrtbase. Прямое подключение к игровому порту без отказника
# работает быстрее (184 с до NeedSpawn против 1204 с) и не перевызывает travel.
s = re.sub(r'"serverAddress": "[^"]*"', '"serverAddress": "192.168.8.218:7777"', s)
s = re.sub(r'"serverAddressFallback": "[^"]*"', '"serverAddressFallback": "192.168.8.218:7777"', s)

io.open(P, "w", encoding="utf-8", newline="\n").write(s)
cfg = json.loads(io.open(P, encoding="utf-8").read())
for k in ("autoConnect", "autoSpawn", "serverAddress", "serverAddressFallback",
          "connectDelaySeconds", "connectFailoverSeconds", "connectRetrySeconds",
          "connectHardRetrySeconds", "characterName", "spawnRegionIndex"):
    if k in cfg:
        print("%-24s = %s" % (k, cfg[k]))
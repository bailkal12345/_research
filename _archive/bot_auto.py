import io
import json
import re

P = r"C:\Dev\ark-bot-research\BotPlayer\Configs\BotPlayer.json"
s = io.open(P, encoding="utf-8").read()

# autoConnect + autoSpawn: бот сам проходит весь цикл (документированный режим),
# я не вмешиваюсь командами и не ловлю гонку с таймерами.
s = re.sub(r'"autoConnect": (true|false)', '"autoConnect": true', s)
s = re.sub(r'"autoSpawn": (true|false)', '"autoSpawn": true', s)
# отказник держим на игровом порту; первый адрес - QueryPort
s = re.sub(r'"serverAddress": "[^"]*"', '"serverAddress": "192.168.8.218:27015"', s)
s = re.sub(r'"serverAddressFallback": "[^"]*"', '"serverAddressFallback": "192.168.8.218:7777"', s)

io.open(P, "w", encoding="utf-8", newline="\n").write(s)
cfg = json.loads(io.open(P, encoding="utf-8").read())
for k in ("enabled", "autoConnect", "autoSpawn", "serverAddress", "serverAddressFallback",
          "connectDelaySeconds", "connectFailoverSeconds", "connectRetrySeconds",
          "connectHardRetrySeconds", "characterName"):
    print("%-24s = %s" % (k, cfg[k]))
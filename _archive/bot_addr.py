import io
import json
import re

P = r"C:\Dev\ark-bot-research\BotPlayer\Configs\BotPlayer.json"
s = io.open(P, encoding="utf-8").read()

# Бот спроектирован под двухступенчатый коннект (docs/GAME_INTERNALS.md 2.4):
#   serverAddress        -> QueryPort сервера (A2S-запрос, из него бот узнаёт Port)
#   serverAddressFallback-> реальный игровой порт
# Наш стенд: QueryPort=27015, Port=7777 (прод-строка RunServer.cmd).
# Я ранее свел оба к 7777 - отказник failover стал бессмысленным.
s = re.sub(r'"serverAddress": "[^"]*"',
           '"serverAddress": "192.168.8.218:27015"', s)
s = re.sub(r'"serverAddressFallback": "[^"]*"',
           '"serverAddressFallback": "192.168.8.218:7777"', s)

io.open(P, "w", encoding="utf-8", newline="\n").write(s)
cfg = json.loads(io.open(P, encoding="utf-8").read())
print("serverAddress        =", cfg["serverAddress"], "(QueryPort, первый этап)")
print("serverAddressFallback=", cfg["serverAddressFallback"], "(игровой порт, отказник)")
print("connectFailoverSeconds =", cfg["connectFailoverSeconds"])
print("connectHardRetrySeconds =", cfg["connectHardRetrySeconds"])
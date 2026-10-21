# -*- coding: utf-8 -*-
import io
p = r"C:\Games\ARK_SE_game_v361\ShooterGame\Binaries\Win64\ArkApi\Plugins\BotPlayer\BotPlayer.json"
s = io.open(p, encoding="utf-8").read()
old = '"connectMethod": "session2",'
new = '"connectMethod": "session2",\n  "sessionSearchWaitSeconds": 90.0,\n  "sessionSearchType": 1,'
assert old in s
io.open(p, "w", encoding="utf-8").write(s.replace(old, new))
print("ok")

import io
p = r"C:\Dev\_research\deploy_map.py"
s = io.open(p, encoding="utf-8", newline="").read()
old_start = s.index("def launch(map_name):")
old_end = s.index("def rcon_ready(")
new = '''def launch(map_name):
    """Прод-строка запуска (Saved/Config/WindowsServer/RunServer.cmd).

    Именно эта строка дважды поднималась нормально, тогда как bench-вариант
    с SessionName=.../RCONEnabled=... замораживал сервер: процесс остаётся жив,
    но CPU = 0 во всех потоках, первый тик не происходит. Флаг -nossteamclient
    задачу не решил (SteamSocketsOpenSource всё равно инициализируется), поэтому
    bench-строка заменена на прод целиком.
    RCON берётся из GameUserSettings.ini: RCONEnabled=True, RCONPort=27020.
    """
    args = ("%s?listen?MultiHome=192.168.8.218?Port=7777?QueryPort=27015"
            "?MaxPlayers=70?AllowCrateSpawnsOnTopOfStructures=True" % map_name)
    flags = ["-EnableIdlePlayerKick", "-NoBattlEye", "-forcerespawndinos",
             "-servergamelog", "-servergamelogincludetribelogs",
             "-ServerRCONOutputTribeLogs", "-NoHangDetection",
             "-noundermeshchecking", "-noundermeshkilling", "-nossteamclient",
             "-game", "-server", "-log", "-MinimumTimeBetweenInventoryRetrieval=3600",
             "-newsaveformat", "-usestore", "-BackupTransferPlayerDatas"]
    cmd = [EXE, args] + flags
    log("запуск (прод-строка, карта %s)" % map_name)
    subprocess.Popen(cmd, cwd=os.path.join(SERVER, "Binaries", "Win64"))


'''
s = s[:old_start] + new + s[old_end:]
io.open(p, "w", encoding="utf-8", newline="").write(s)
import ast; ast.parse(s)
print("launch() заменён, синтаксис ок")

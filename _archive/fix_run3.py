import io
p = "run_measure.py"
s = io.open(p, encoding="utf-8").read()
# UWorld.Tick держит сам ArkApi, второй хук на нём роняет сервер — убираем из списка
s = s.replace('''    (1, "UEngine.Tick"),
    (2, "UWorld.Tick"),
]''', '''    (1, "UEngine.Tick"),
    # (2, "UWorld.Tick") — на нём уже висит хук ArkApi (CheckOnTickCallbacks);
    # второй хук в цепочке роняет сервер, проверено.
]''')
# ждём файлы артефактов после stop
s = s.replace('''    for f in sorted(os.listdir(PLUGIN_DIR)):''',
'''    for _ in range(30):
        if any(f.startswith("prof_") for f in os.listdir(PLUGIN_DIR)):
            break
        time.sleep(2)

    for f in sorted(os.listdir(PLUGIN_DIR)):''')
io.open(p, "w", encoding="utf-8").write(s)
print("patched run_measure")

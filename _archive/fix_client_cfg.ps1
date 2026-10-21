$ErrorActionPreference = 'Stop'

# Правка ТОЛЬКО в развёрнутом конфиге клиента. Репозиторий бота остаётся
# откатанным (79e7286) - здесь выставляется адрес стенда: сервер слушает
# Port=7777 / QueryPort=27015, тогда как в откате стоит 27016/7778.
# Длинный failover нужен, чтобы не рвать незавершённый Browse_Pending:
# Hooks.cpp документирует повторный SetClientTravel как путь к __fastfail.
$cfgPath = 'C:\Games\ARK_SE_game_v361\ShooterGame\Binaries\Win64\ArkApi\Plugins\BotPlayer\BotPlayer.json'
$t = Get-Content $cfgPath -Raw
$t = $t -replace '"serverAddress": "[^"]*"', '"serverAddress": "192.168.8.218:27015"'
$t = $t -replace '"serverAddressFallback": "[^"]*"', '"serverAddressFallback": "192.168.8.218:27015"'
$t = $t -replace '"connectFailoverSeconds": [0-9.]+', '"connectFailoverSeconds": 1200.0'
Set-Content -Path $cfgPath -Value $t -Encoding utf8

(Get-Content $cfgPath -Raw | ConvertFrom-Json) |
  Select-Object autoConnect, autoSpawn, serverAddress, serverAddressFallback, connectFailoverSeconds |
  Format-List | Out-String
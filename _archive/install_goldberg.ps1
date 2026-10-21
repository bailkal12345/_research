$ErrorActionPreference = 'Stop'

$GAME = 'C:\Games\ARK_SE_game_v361\ShooterGame\Binaries\Win64'
$EMU  = 'C:\Users\Admin\AppData\Local\Temp\opencode\gbe\release\experimental\x64'
$BK   = 'C:\Dev\_research\steam_backup'
$EXAMPLES = 'C:\Users\Admin\AppData\Local\Temp\opencode\gbe\release\steam_settings.EXAMPLE'

New-Item -ItemType Directory -Path $BK -Force | Out-Null

# 1) бэкап всего, что лежит в каталоге клиента и относится к Steam
foreach ($f in @('steamclient64.dll','steam_api64.dll')) {
  $p = Join-Path $GAME $f
  if (Test-Path $p) {
    Copy-Item $p (Join-Path $BK $f) -Force
    "бэкап: $f"
  }
}

# 2) эмулятор
foreach ($f in @('steam_api64.dll','steamclient64.dll')) {
  $dll = Join-Path $EMU $f
  if (Test-Path $dll) {
    Copy-Item $dll (Join-Path $GAME $f) -Force
    "установлен: $f ({0:N0} байт)" -f (Get-Item (Join-Path $GAME $f)).Length
  }
}

# 3) steam_settings
$SS = Join-Path $GAME 'steam_settings'
Remove-Item $SS -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $SS -Force | Out-Null

Set-Content -Path (Join-Path $SS 'steam_appid.txt') -Value '346110' -Encoding ascii -NoNewline
"steam_appid.txt = 346110"

foreach ($f in @('configs.app.EXAMPLE.ini','configs.main.EXAMPLE.ini','configs.user.EXAMPLE.ini','configs.overlay.EXAMPLE.ini')) {
  $name = $f -replace '\.EXAMPLE\.ini$', '.ini'
  Copy-Item (Join-Path $EXAMPLES $f) (Join-Path $SS $name) -Force
  "шаблон -> $name"
}

# 4) открыть все DLC
$app = Join-Path $SS 'configs.app.ini'
$t = Get-Content $app -Raw
$t = $t -replace '(?m)^unlock_all=0', 'unlock_all=1'
Set-Content -Path $app -Value $t -Encoding utf8
"configs.app.ini: [app::dlcs] unlock_all=1"

# 5) сеть эмулятора не выключаем - клиент должен достучаться до сервера
$main = Join-Path $SS 'configs.main.ini'
$m = Get-Content $main -Raw
$m = $m -replace '(?m)^disable_networking=0', 'disable_networking=0'
$m = $m -replace '(?m)^enable_steam_preowned_ids=0', 'enable_steam_preowned_ids=1'
Set-Content -Path $main -Value $m -Encoding utf8
"configs.main.ini: disable_networking=0, enable_steam_preowned_ids=1"

# 6) аккаунт
$user = Join-Path $SS 'configs.user.ini'
$u = Get-Content $user -Raw
$u = $u -replace '(?m)^account_name=.*$', 'account_name=bench'
$u = $u -replace '(?m)^account_steamid=.*$', 'account_steamid=76561197960287930'
Set-Content -Path $user -Value $u -Encoding utf8
"configs.user.ini: account_name=bench"

# 7) старый steam_appid.txt клиента оставляем (он даёт appid при запуске напрямую)
"готово. Откат: скопировать $BK\*.dll обратно в $GAME и удалить $SS"
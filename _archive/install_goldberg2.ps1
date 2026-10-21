$ErrorActionPreference = 'Stop'

$GAME    = 'C:\Games\ARK_SE_game_v361\ShooterGame\Binaries\Win64'
$SW      = 'C:\Games\ARK_SE_game_v361\Engine\Binaries\ThirdParty\Steamworks\Steamv132\Win64'
$EMU     = 'C:\Users\Admin\AppData\Local\Temp\opencode\gbe\release\experimental\x64'
$EXAMPLES= 'C:\Users\Admin\AppData\Local\Temp\opencode\gbe\release\steam_settings.EXAMPLE'
$BK      = 'C:\Dev\_research\steam_backup'

"Steamworks-каталог существует: " + (Test-Path $SW)
Get-ChildItem $SW -Filter 'steam*.dll' | ForEach-Object { "было: {0} {1:N0} байт" -f $_.Name, $_.Length }

New-Item -ItemType Directory -Path $BK -Force | Out-Null

# 1) бэкап оригиналов Steamworks
foreach ($f in @('steam_api64.dll','steamclient64.dll')) {
  $p = Join-Path $SW $f
  if (Test-Path $p) {
    Copy-Item $p (Join-Path $BK ("sw_" + $f)) -Force
    "бэкап: Steamworks\$f"
  }
}

# 2) эмулятор в Steamworks-каталог
foreach ($f in @('steam_api64.dll','steamclient64.dll')) {
  $dll = Join-Path $EMU $f
  if (Test-Path $dll) {
    Copy-Item $dll (Join-Path $SW $f) -Force
    "установлен: Steamworks\$f ({0:N0} байт)" -f (Get-Item (Join-Path $SW $f)).Length
  }
}

# 3) steam_settings рядом с DLL - эмулятор ищет её относительно своего пути
$SS = Join-Path $SW 'steam_settings'
Remove-Item $SS -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $SS -Force | Out-Null
Set-Content -Path (Join-Path $SS 'steam_appid.txt') -Value '346110' -Encoding ascii -NoNewline
foreach ($f in @('configs.app.EXAMPLE.ini','configs.main.EXAMPLE.ini','configs.user.EXAMPLE.ini','configs.overlay.EXAMPLE.ini')) {
  Copy-Item (Join-Path $EXAMPLES $f) (Join-Path $SS ($f -replace '\.EXAMPLE\.ini$', '.ini')) -Force
}

$app = Join-Path $SS 'configs.app.ini'
(Get-Content $app -Raw) -replace '(?m)^unlock_all=0', 'unlock_all=1' | Set-Content $app -Encoding utf8
$main = Join-Path $SS 'configs.main.ini'
(Get-Content $main -Raw) -replace '(?m)^enable_steam_preowned_ids=0', 'enable_steam_preowned_ids=1' | Set-Content $main -Encoding utf8
$user = Join-Path $SS 'configs.user.ini'
(Get-Content $user -Raw) -replace '(?m)^account_name=.*$', 'account_name=bench' | Set-Content $user -Encoding utf8

"[app::dlcs] unlock_all=1; steam_appid.txt=346110; account_name=bench"
"Откат: скопировать $BK\sw_*.dll обратно в $SW и удалить $SS"
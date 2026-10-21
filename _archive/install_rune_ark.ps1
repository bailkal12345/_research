$ErrorActionPreference = 'Stop'

$GAME = 'C:\Games\ARK_SE_game_v361'
$SRC  = 'C:\Users\Admin\AppData\Local\Temp\opencode\crack\rune\RUNE'
$BK   = 'C:\Dev\_research\steam_backup'

$swWin64   = Join-Path $GAME 'Engine\Binaries\ThirdParty\Steamworks\Steamv132\Win64'
$gameWin64 = Join-Path $GAME 'ShooterGame\Binaries\Win64'

# 1) снимаем то, что ставил раньше (Goldberg / самодельный RUNE)
Remove-Item (Join-Path $gameWin64 'steam_settings') -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $swWin64 'steam_settings')   -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $swWin64 'steam_emu.ini')   -Force -ErrorAction SilentlyContinue

# 2) бэкап того, что заменяем (оригиналы уже есть в архиве как .rne, но пусть будет свой бэкап)
foreach ($p in @((Join-Path $swWin64 'steam_api64.dll'), (Join-Path $gameWin64 'steamclient64.dll'))) {
  if (Test-Path $p) {
    Copy-Item $p (Join-Path $BK ("preinstall_" + (Split-Path $p -Leaf))) -Force
    "бэкап: $p"
  }
}

# 3) ставим RUNE по родной раскладке
#    steam_emu.ini нужен в ОБОИХ каталогах: у клиента Steam читает его рядом
#    с exe, у движка - рядом с steam_api64.dll. Без второго был config error.
Copy-Item (Join-Path $SRC 'ShooterGame\Binaries\Win64\steam_emu.ini') $gameWin64 -Force
Copy-Item (Join-Path $SRC 'ShooterGame\Binaries\Win64\steamclient64.dll') $gameWin64 -Force
Copy-Item (Join-Path $SRC 'Engine\Binaries\ThirdParty\Steamworks\Steamv132\Win64\steam_api64.dll') $swWin64 -Force
Copy-Item (Join-Path $SRC 'Engine\Binaries\ThirdParty\Steamworks\Steamv132\Win64\steam_emu.ini') $swWin64 -Force

# 4) открываем все DLC в ОБОИХ ini
foreach ($ini in @((Join-Path $gameWin64 'steam_emu.ini'), (Join-Path $swWin64 'steam_emu.ini'))) {
  $t = Get-Content $ini -Raw
  $t = $t -replace '(?m)^DLCUnlockall=0', 'DLCUnlockall=1'
  Set-Content -Path $ini -Value $t -Encoding ascii -NoNewline
  "DLCUnlockall=1 -> $ini"
}

"=== итог ==="
Get-ChildItem $gameWin64 -Filter 'steam*' | ForEach-Object { "game  {0,-22} {1,12:N0} байт" -f $_.Name, $_.Length }
Get-ChildItem $swWin64   -Filter 'steam*' | ForEach-Object { "steam {0,-22} {1,12:N0} байт" -f $_.Name, $_.Length }
$ErrorActionPreference = 'Stop'

$GAME = 'C:\Games\ARK_SE_game_v361'
$SRC  = 'C:\Users\Admin\AppData\Local\Temp\opencode\crack\codex\CODEX'

$swWin64   = Join-Path $GAME 'Engine\Binaries\ThirdParty\Steamworks\Steamv132\Win64'
$gameWin64 = Join-Path $GAME 'ShooterGame\Binaries\Win64'

# снимаем RUNE
foreach ($f in @('steam_emu.ini')) {
  Remove-Item (Join-Path $gameWin64 $f) -Force -ErrorAction SilentlyContinue
  Remove-Item (Join-Path $swWin64   $f) -Force -ErrorAction SilentlyContinue
}

# CODEX: Steamworks-часть
Copy-Item (Join-Path $SRC 'Engine\Binaries\ThirdParty\Steamworks\Steamv132\Win64\codex64.dll')             $swWin64 -Force
Copy-Item (Join-Path $SRC 'Engine\Binaries\ThirdParty\Steamworks\Steamv132\Win64\GameOverlayRenderer64.dll') $swWin64 -Force
Copy-Item (Join-Path $SRC 'Engine\Binaries\ThirdParty\Steamworks\Steamv132\Win64\steam_api64.dll')          $swWin64 -Force
Copy-Item (Join-Path $SRC 'Engine\Binaries\ThirdParty\Steamworks\Steamv132\Win64\steam_emu.ini')            $swWin64 -Force

# CODEX: игровая часть
Copy-Item (Join-Path $SRC 'ShooterGame\Binaries\Win64\steamclient64.dll') $gameWin64 -Force
Copy-Item (Join-Path $SRC 'ShooterGame\Binaries\Win64\steam_emu.ini')      $gameWin64 -Force

# открыть все DLC в обоих ini
foreach ($ini in @((Join-Path $gameWin64 'steam_emu.ini'), (Join-Path $swWin64 'steam_emu.ini'))) {
  $t = Get-Content $ini -Raw
  $t = $t -replace '(?m)^DLCUnlockall=0', 'DLCUnlockall=1'
  Set-Content -Path $ini -Value $t -Encoding ascii -NoNewline
  "DLCUnlockall=1 -> $ini"
}

"=== итог ==="
Get-ChildItem $gameWin64 -Filter 'steam*' | ForEach-Object { "game  {0,-24} {1,12:N0} байт" -f $_.Name, $_.Length }
Get-ChildItem $swWin64   -Filter '*.dll'  | Where-Object { $_.Name -match 'steam|codex|GameOverlay' } | ForEach-Object { "steam {0,-24} {1,12:N0} байт" -f $_.Name, $_.Length }
"=== ключевые строки ini:"
Select-String -Path (Join-Path $gameWin64 'steam_emu.ini') -Pattern 'AppId|Language|LobbyEnabled|Offline|DLCUnlockall' | ForEach-Object { "  " + $_.Line.Trim() }
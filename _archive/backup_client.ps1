$ErrorActionPreference = 'Continue'

$ROOT = 'C:\Games\ARK_SE_game_v361'
$GAME = Join-Path $ROOT 'ShooterGame\Binaries\Win64'
$SW   = Join-Path $ROOT 'Engine\Binaries\ThirdParty\Steamworks\Steamv132\Win64'
$BK   = 'C:\Users\Admin\AppData\Local\Temp\opencode\ark361_backup_20261019'

New-Item -ItemType Directory -Path $BK -Force | Out-Null

# Относительный путь -> источник. Steam-подсистема плюс всё, что менялось
# в этой сессии (загрузчик Arksharp, msdia140, плагин бота).
$targets = @(
  'Engine\Binaries\ThirdParty\Steamworks\Steamv132\Win64\steam_api64.dll',
  'Engine\Binaries\ThirdParty\Steamworks\Steamv132\Win64\steamclient64.dll',
  'Engine\Binaries\ThirdParty\Steamworks\Steamv132\Win64\steam_emu.ini',
  'ShooterGame\Binaries\Win64\steamclient64.dll',
  'ShooterGame\Binaries\Win64\steam_api64.dll',
  'ShooterGame\Binaries\Win64\steam_emu.ini',
  'ShooterGame\Binaries\Win64\steam_appid.txt',
  'ShooterGame\Binaries\Win64\version.dll',
  'ShooterGame\Binaries\Win64\version.pdb',
  'ShooterGame\Binaries\Win64\version.dll_',
  'ShooterGame\Binaries\Win64\config.json',
  'ShooterGame\Binaries\Win64\msdia140.dll',
  'ShooterGame\Binaries\Win64\ArkApi\Plugins\BotPlayer\BotPlayer.dll',
  'ShooterGame\Binaries\Win64\ArkApi\Plugins\BotPlayer\BotPlayer.json',
  'ShooterGame\Binaries\Win64\ArkApi\Plugins\BotPlayer\PluginInfo.json'
)

$manifest = @()
foreach ($rel in $targets) {
  $src = Join-Path $ROOT $rel
  $dst = Join-Path $BK $rel
  if (Test-Path $src) {
    New-Item -ItemType Directory -Path (Split-Path $dst) -Force | Out-Null
    try {
      Copy-Item $src $dst -Force
      $len = (Get-Item $src).Length
      $sha = (Get-FileHash $src -Algorithm SHA256).Hash
      $manifest += [pscustomobject]@{ file=$rel; bytes=$len; sha256=$sha; state='сохранён' }
    } catch {
      $manifest += [pscustomobject]@{ file=$rel; bytes=(Get-Item $src).Length; sha256='-'; state="НЕ СКОПИРОВАН: $($_.Exception.Message)" }
    }
  } else {
    $manifest += [pscustomobject]@{ file=$rel; bytes=0; sha256='-'; state='отсутствует в клиенте' }
  }
}

# каталоги, которые создаёт эмулятор и которые надо убрать при откате
foreach ($d in @('ShooterGame\Binaries\Win64\steam_settings',
                 'Engine\Binaries\ThirdParty\Steamworks\Steamv132\Win64\steam_settings')) {
  $p = Join-Path $ROOT $d
  if (Test-Path $p) {
    $rd = Join-Path $BK ("_DIRS\" + ($d -replace '[\\]','__'))
    New-Item -ItemType Directory -Path (Split-Path $rd) -Force | Out-Null
    Copy-Item $p $rd -Recurse -Force
    $manifest += [pscustomobject]@{ file=$d; bytes=0; sha256='-'; state='каталог сохранён (удалить при откате)' }
  }
}

$manifest | Format-Table -AutoSize | Out-String -Width 150 | Write-Host
$manifest | Export-Csv -Path (Join-Path $BK 'MANIFEST.csv') -NoTypeInformation -Encoding utf8
"бэкап: $BK"
"MАНИФЕСТ: $(Join-Path $BK 'MANIFEST.csv')"
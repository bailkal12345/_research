$ErrorActionPreference = 'Continue'

# Откат клиента ARK v361 к состоянию до установки Steam-эмулятора.
# Клиент при этом должен быть закрыт: DLL заняты работающим процессом.
$ROOT = 'C:\Games\ARK_SE_game_v361'
$BK   = 'C:\Users\Admin\AppData\Local\Temp\opencode\ark361_backup_20261019'

if (-not (Test-Path $BK)) { "нет бэкапа: $BK"; exit 1 }

$running = Get-Process ShooterGame -ErrorAction SilentlyContinue
if ($running) {
  "ВНИМАНИЕ: клиент запущен (pid $($running.Id -join ',')). Закройте его и повторите."
  "Для отката DLL файлы должны быть свободны."
  exit 2
}

$man = Import-Csv (Join-Path $BK 'MANIFEST.csv')
$restored = 0; $skipped = 0; $missing = 0

foreach ($row in $man) {
  $src = Join-Path $BK $row.file
  $dst = Join-Path $ROOT $row.file
  if ($row.state -like 'отсутствует*') { $missing++; continue }   # такого файла не было - откатывать нечего
  if (-not (Test-Path $src)) { "нет в бэкапе: $($row.file)"; $skipped++; continue }
  New-Item -ItemType Directory -Path (Split-Path $dst) -Force | Out-Null
  Copy-Item $src $dst -Force
  $restored++
}

# каталоги эмулятора - удалить
$dirs = @('ShooterGame\Binaries\Win64\steam_settings',
          'Engine\Binaries\ThirdParty\Steamworks\Steamv132\Win64\steam_settings')
foreach ($d in $dirs) {
  $p = Join-Path $ROOT $d
  $marker = Join-Path $BK ("_DIRS\" + ($d -replace '[\\]','__'))
  if ((Test-Path $p) -and (Test-Path $marker)) {
    Remove-Item $p -Recurse -Force
    "удалён каталог эмулятора: $d"
  }
}

"восстановлено файлов: $restored"
"пропущено (отсутствовали): $missing"
"пропущено (нет в бэкапе): $skipped"
param(
    [ValidateSet("stock", "plugin")][string]$Mode = "stock",
    [string]$RestoreSave = "",
    [string]$SnapshotOut = "",
    [string]$Dll = "C:\Dev\ARK-Server-Plugins\EngineSwap\Mimalloc\build\Release\Mimalloc.dll",
    [switch]$SkipStop,
    [int]$ExitTimeoutSec = 120,
    [int]$LoadTimeoutSec = 900
)
$ErrorActionPreference = "Continue"
$serverRoot = "C:\asmdata\Servers\Server2"
$bin = Join-Path $serverRoot "ShooterGame\Binaries\Win64"
$exe = Join-Path $bin "ShooterGameServer.exe"
$plugins = Join-Path $bin "ArkApi\Plugins"
$miDir = Join-Path $plugins "Mimalloc"
$miSrc = $Dll
$args = "TheIsland?listen?MultiHome=192.168.8.218?Port=7778?QueryPort=27016?MaxPlayers=70?AllowCrateSpawnsOnTopOfStructures=True -EnableIdlePlayerKick -NoBattlEye -insecure -servergamelog -servergamelogincludetribelogs -ServerRCONOutputTribeLogs -NoHangDetection -noundermeshchecking -noundermeshkilling -NoDinos -nosteamclient -game -server -log -MinimumTimeBetweenInventoryRetrieval=3600"
$env:RCON_HOST = "192.168.8.218"
$env:RCON_PORT = "32331"
$env:RCON_PASS = "9dzeZuoCBQJ7adMT"
$rcon = "C:\Dev\_research\rcon.py"

function Say($m) { Write-Output ("[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $m) }

# ---- stop (match by executable path: both servers run ShooterGameServer.exe)
$proc = Get-Process -Name ShooterGameServer -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -eq $exe } | Select-Object -First 1
$other = Get-Process -Name ShooterGameServer -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -ne $exe } | ForEach-Object { Say "NOTE: another server is running (PID $($_.Id), $($_.Path)) - left alone" }
if ($proc -and $SkipStop) {
    Say "skipping stop (server is already down)"
} elseif ($proc) {
    Say "stopping PID $($proc.Id) (SaveWorld + Exit)"
    py $rcon "SaveWorld" | Out-Null
    Start-Sleep -Seconds 20
    py $rcon "Exit" | Out-Null
    $deadline = (Get-Date).AddSeconds(90)
    while ((Get-Date) -lt $deadline) {
        if (-not (Get-Process -Id $proc.Id -ErrorAction SilentlyContinue)) { break }
        Start-Sleep -Seconds 10
    }
    if (Get-Process -Id $proc.Id -ErrorAction SilentlyContinue) {
        Say "RCON Exit ignored; terminating PID $($proc.Id) (world is saved)"
        Stop-Process -Id $proc.Id -Force
        Start-Sleep -Seconds 15
    }
    Say "process exited"
} else {
    Say "server not running"
}
Start-Sleep -Seconds 10

# ---- plugin state
if ($Mode -eq "plugin") {
    New-Item -ItemType Directory -Force -Path $miDir | Out-Null
    Copy-Item $miSrc (Join-Path $miDir "Mimalloc.dll") -Force
    $pdb = [IO.Path]::ChangeExtension($miSrc, ".pdb")
    if (Test-Path $pdb) { Copy-Item $pdb (Join-Path $miDir "Mimalloc.pdb") -Force }
    if (Test-Path (Join-Path $miDir "Mimalloc.log")) { Remove-Item (Join-Path $miDir "Mimalloc.log") -Force }
    Say "deployed mimalloc: $((Get-Item (Join-Path $miDir 'Mimalloc.dll')).Length) bytes"
} else {
    if (Test-Path $miDir) {
        Rename-Item -Path $miDir -NewName "Mimalloc.off" -Force -ErrorAction SilentlyContinue
        if (Test-Path $miDir) { Remove-Item $miDir -Recurse -Force -ErrorAction SilentlyContinue }
    }
    Say "mimalloc removed from plugins"
}

# ---- world snapshot (taken after the stop, before the start)
if ($SnapshotOut) {
    $saved = Join-Path $serverRoot "ShooterGame\Saved\SavedArks"
    $src = Join-Path $saved "TheIsland.ark"
    if (Test-Path $src) {
        New-Item -ItemType Directory -Force -Path (Split-Path $SnapshotOut) | Out-Null
        Copy-Item $src $SnapshotOut -Force
        Say "world snapshot -> $SnapshotOut ($((Get-Item $SnapshotOut).Length) bytes)"
    } else {
        Say "WARNING: no world file to snapshot"
    }
}

# ---- restore world snapshot
if ($RestoreSave -and (Test-Path $RestoreSave)) {
    $saved = Join-Path $serverRoot "ShooterGame\Saved\SavedArks"
    $dest = Join-Path $saved "TheIsland.ark"
    $snapTime = (Get-Item $RestoreSave).LastWriteTime
    Get-ChildItem $saved -Filter "TheIsland_*.ark" -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -gt $snapTime } |
        ForEach-Object { Remove-Item $_.FullName -Force; Say "removed newer rotation $($_.Name)" }
    Copy-Item $RestoreSave $dest -Force
    Say "restored world save -> $dest ($((Get-Item $dest).Length) bytes)"
}

# ---- start
$logDir = Join-Path $bin "logs"
$before = @(Get-ChildItem $logDir -Filter "ArkApi_*.log" -ErrorAction SilentlyContinue | ForEach-Object { $_.Name })
$p = Start-Process -FilePath $exe -ArgumentList $args -WorkingDirectory $bin -PassThru
Say "started PID $($p.Id)"

# ---- wait for world load
$deadline = (Get-Date).AddSeconds($LoadTimeoutSec)
$loaded = $false
while ((Get-Date) -lt $deadline) {
    if (-not (Get-Process -Id $p.Id -ErrorAction SilentlyContinue)) { Say "process died during startup"; exit 3 }    $new = Get-ChildItem $logDir -Filter "ArkApi_*.log" -ErrorAction SilentlyContinue |
        Where-Object { $before -notcontains $_.Name } | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($new) {
        $hit = Select-String -Path $new.FullName -Pattern "UWorld::InitWorld was called" -SimpleMatch -ErrorAction SilentlyContinue
        if ($hit) { $loaded = $true; Say "world loaded at $($hit[0].Line)"; break }
    }
    Start-Sleep -Seconds 15
}
if (-not $loaded) { Say "WARNING: world load not confirmed within $LoadTimeoutSec s" }
Say "phase $Mode ready: PID $($p.Id), world loaded=$loaded, time $(Get-Date -Format 'HH:mm:ss')"

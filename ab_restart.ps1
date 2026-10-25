param(
    [ValidateSet("stock", "plugin")][string]$Mode = "stock",
    [string]$RestoreSave = "",
    [string]$Dll = "C:\Dev\ARK-Server-Plugins\mimalloc\build\Release\mimalloc.dll",
    [switch]$SkipStop,
    [int]$ExitTimeoutSec = 420,
    [int]$LoadTimeoutSec = 900
)
$ErrorActionPreference = "Continue"
$serverRoot = "C:\asmdata\Servers\Server1"
$bin = Join-Path $serverRoot "ShooterGame\Binaries\Win64"
$exe = Join-Path $bin "ShooterGameServer.exe"
$plugins = Join-Path $bin "ArkApi\Plugins"
$miDir = Join-Path $plugins "mimalloc"
$miSrc = $Dll
$args = "Genesis?listen?MultiHome=192.168.8.218?Port=7777?QueryPort=27015?MaxPlayers=70?AllowCrateSpawnsOnTopOfStructures=True -EnableIdlePlayerKick -NoBattlEye -insecure -forcerespawndinos -servergamelog -servergamelogincludetribelogs -ServerRCONOutputTribeLogs -NoHangDetection -noundermeshchecking -noundermeshkilling -nosteamclient -game -server -log -MinimumTimeBetweenInventoryRetrieval=3600 -newsaveformat -usestore -BackupTransferPlayerDatas"
$env:RCON_HOST = "192.168.8.218"
$env:RCON_PORT = "32330"
$env:RCON_PASS = "0ub7OuAD6V68cbzc"
$rcon = "C:\Dev\_research\abrcon.py"

function Say($m) { Write-Output ("[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $m) }

# ---- stop
$proc = Get-Process -Name ShooterGameServer -ErrorAction SilentlyContinue | Select-Object -First 1
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
    if (Get-Process -Id $proc.Id -ErrorAction SilentlyContinue) {
        Say "graceful exit timed out after $ExitTimeoutSec s"
        exit 2
    }
    Say "process exited"
} else {
    Say "server not running"
}
Start-Sleep -Seconds 10

# ---- plugin state
if ($Mode -eq "plugin") {
    New-Item -ItemType Directory -Force -Path $miDir | Out-Null
    Copy-Item $miSrc (Join-Path $miDir "mimalloc.dll") -Force
    $pdb = [IO.Path]::ChangeExtension($miSrc, ".pdb")
    if (Test-Path $pdb) { Copy-Item $pdb (Join-Path $miDir "mimalloc.pdb") -Force }
    if (Test-Path (Join-Path $miDir "mimalloc.log")) { Remove-Item (Join-Path $miDir "mimalloc.log") -Force }
    Say "deployed mimalloc: $((Get-Item (Join-Path $miDir 'mimalloc.dll')).Length) bytes"
} else {
    if (Test-Path $miDir) {
        Rename-Item -Path $miDir -NewName "mimalloc.off" -Force -ErrorAction SilentlyContinue
        if (Test-Path $miDir) { Remove-Item $miDir -Recurse -Force -ErrorAction SilentlyContinue }
    }
    Say "mimalloc removed from plugins"
}

# ---- other allocator plugins must stay disabled
Get-ChildItem $plugins -Recurse -Filter "*.dll" -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like "EngineSwap*" -and $_.Name -notlike "*.off" } |
    ForEach-Object { Rename-Item $_.FullName ($_.FullName + ".off") -Force; Say "disabled $($_.Name)" }

# ---- restore world snapshot
if ($RestoreSave -and (Test-Path $RestoreSave)) {
    $saved = Join-Path $serverRoot "ShooterGame\Saved\SavedArks"
    $dest = Join-Path $saved "Genesis.ark"
    $snapTime = (Get-Item $RestoreSave).LastWriteTime
    Get-ChildItem $saved -Filter "Genesis_*.ark" -ErrorAction SilentlyContinue |
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
    if (-not (Get-Process -Id $p.Id -ErrorAction SilentlyContinue)) { Say "process died during startup"; exit 3 }
    $new = Get-ChildItem $logDir -Filter "ArkApi_*.log" -ErrorAction SilentlyContinue |
        Where-Object { $before -notcontains $_.Name } | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($new) {
        $hit = Select-String -Path $new.FullName -Pattern "UWorld::InitWorld was called" -SimpleMatch -ErrorAction SilentlyContinue
        if ($hit) { $loaded = $true; Say "world loaded at $($hit[0].Line)"; break }
    }
    Start-Sleep -Seconds 15
}
if (-not $loaded) { Say "WARNING: world load not confirmed within $LoadTimeoutSec s" }
Say "phase $Mode ready: PID $($p.Id), world loaded=$loaded, time $(Get-Date -Format 'HH:mm:ss')"

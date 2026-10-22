param(
    [Parameter(Mandatory = $true)][string]$Label,
    [int]$WarmupSec = 600,
    [int]$WindowSec = 1800
)
$env:RCON_HOST = "192.168.8.218"
$env:RCON_PORT = "32330"
$rcon = "C:\Dev\_research\rcon.py"
$sampler = "C:\Dev\_research\ab_sampler.ps1"
$tickLog = "C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi\Plugins\TickProf\TickProf.log"

Write-Output ("[{0}] warmup {1}s" -f (Get-Date -Format "HH:mm:ss"), $WarmupSec)
Start-Sleep -Seconds $WarmupSec

$before = (Get-Content $tickLog | Measure-Object -Line).Lines
Write-Output ("[{0}] window {1}s" -f (Get-Date -Format "HH:mm:ss"), $WindowSec)
py $rcon "TickProf.window $WindowSec" | Out-Null

& pwsh -NoProfile -ExecutionPolicy Bypass -File $sampler -Label $Label -Seconds $WindowSec -Interval 30 | Out-Null

$after = Get-Content $tickLog | Select-Object -Skip $before
Write-Output ("[{0}] window result:" -f (Get-Date -Format "HH:mm:ss"))
$after | Where-Object { $_ -match "window" } | ForEach-Object { Write-Output $_ }
Write-Output ("[{0}] phase {1} done" -f (Get-Date -Format "HH:mm:ss"), $Label)

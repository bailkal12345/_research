param(
    [Parameter(Mandatory = $true)][string]$Label,
    [int]$WarmupSec = 600,
    [int]$WindowSec = 1800
)
$env:RCON_HOST = "192.168.8.218"
$env:RCON_PORT = "32330"
$env:RCON_PASS = "0ub7OuAD6V68cbzc"
$rcon = "C:\Dev\_research\abrcon.py"
$sampler = "C:\Dev\_research\ab_sampler.ps1"
$tickLog = "C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ArkApi\Plugins\TickProf\TickProf.log"
$hasTickProf = Test-Path $tickLog

Write-Output ("[{0}] warmup {1}s" -f (Get-Date -Format "HH:mm:ss"), $WarmupSec)
Start-Sleep -Seconds $WarmupSec

if ($hasTickProf) { $before = (Get-Content $tickLog | Measure-Object -Line).Lines }
Write-Output ("[{0}] window {1}s (TickProf: {2})" -f (Get-Date -Format "HH:mm:ss"), $WindowSec, $hasTickProf)
if ($hasTickProf) { py $rcon "TickProf.window $WindowSec" | Out-Null }

& pwsh -NoProfile -ExecutionPolicy Bypass -File $sampler -Label $Label -Seconds $WindowSec -Interval 30 | Out-Null

if ($hasTickProf) {
    Write-Output ("[{0}] window result:" -f (Get-Date -Format "HH:mm:ss"))
    Get-Content $tickLog | Select-Object -Skip $before | Where-Object { $_ -match "window" } | ForEach-Object { Write-Output $_ }
}
Write-Output ("[{0}] phase {1} done" -f (Get-Date -Format "HH:mm:ss"), $Label)

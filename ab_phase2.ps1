param(
    [Parameter(Mandatory = $true)][string]$Label,
    [int]$WarmupSec = 600,
    [int]$WindowSec = 1800
)
$env:RCON_HOST = "192.168.8.218"
$env:RCON_PORT = "32331"
$env:RCON_PASS = "9dzeZuoCBQJ7adMT"
$exe = "C:\asmdata\Servers\Server2\ShooterGame\Binaries\Win64\ShooterGameServer.exe"
$sampler = "C:\Dev\_research\ab_sampler.ps1"
$ngSampler = "C:\Dev\_research\ab_ng_sampler.py"

Write-Output ("[{0}] warmup {1}s" -f (Get-Date -Format "HH:mm:ss"), $WarmupSec)
Start-Sleep -Seconds $WarmupSec

Write-Output ("[{0}] window {1}s" -f (Get-Date -Format "HH:mm:ss"), $WindowSec)
& py $ngSampler $Label $WindowSec 10 | Out-Null
& pwsh -NoProfile -ExecutionPolicy Bypass -File $sampler -Label $Label -Seconds $WindowSec -Interval 30 -ExePath $exe | Out-Null
Write-Output ("[{0}] phase {1} done" -f (Get-Date -Format "HH:mm:ss"), $Label)

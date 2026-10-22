param(
    [Parameter(Mandatory = $true)][string]$Label,
    [int]$Seconds = 1800,
    [int]$Interval = 30,
    [string]$Out = "",
    [string]$ExePath = "C:\asmdata\Servers\Server1\ShooterGame\Binaries\Win64\ShooterGameServer.exe"
)
$dir = "C:\Dev\_research\ab"
New-Item -ItemType Directory -Force -Path $dir | Out-Null
$csv = if ($Out) { $Out } else { Join-Path $dir "$Label.csv" }
$inv = [cultureinfo]::InvariantCulture
"ts,pid,uptime_s,cpu_s,ws_mb,priv_mb,handles,threads,pagefaults" | Set-Content -Path $csv -Encoding utf8
$end = (Get-Date).AddSeconds($Seconds)
while ((Get-Date) -lt $end) {
    $p = Get-Process -Name ShooterGameServer -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -eq $ExePath } | Select-Object -First 1
    if ($p) {
        $c = Get-CimInstance Win32_Process -Filter "ProcessId=$($p.Id)"
        $row = [string]::Format($inv, "{0},{1},{2},{3:0.0},{4:0.0},{5:0.0},{6:0},{7:0},{8:0}",
            (Get-Date -Format "yyyy-MM-dd HH:mm:ss"),
            $p.Id,
            [math]::Round(((Get-Date) - $p.StartTime).TotalSeconds, 0),
            $p.CPU,
            ($p.WorkingSet64 / 1MB),
            ($p.PrivateMemorySize64 / 1MB),
            $p.HandleCount,
            $p.Threads.Count,
            $c.PageFaults)
        Add-Content -Path $csv -Value $row -Encoding utf8
    }
    Start-Sleep -Seconds $Interval
}
Write-Output "sampler done: $csv"

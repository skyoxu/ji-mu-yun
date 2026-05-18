$ErrorActionPreference = 'Stop'

$watchdogPidFile = 'C:\jimuyun\logs\phase-a-innernet\phasea-watchdog.pid'
$runtimeLogRoot = 'C:\jimuyun\logs\phase-a-innernet\runtime'
$watchdogLog = Join-Path $runtimeLogRoot 'phasea-watchdog.log'
$ensureScript = 'C:\jimuyun\runtime\phase-a\ensure-phasea.ps1'
$intervalSeconds = 30

New-Item -ItemType Directory -Force -Path $runtimeLogRoot | Out-Null
Set-Content -Path $watchdogPidFile -Value $PID -Encoding ascii

while ($true) {
    $timestamp = [DateTime]::UtcNow.ToString('o')
    Add-Content -Path $watchdogLog -Value "$timestamp phasea-watchdog tick"
    try {
        & $ensureScript | ForEach-Object { Add-Content -Path $watchdogLog -Value $_ }
    }
    catch {
        Add-Content -Path $watchdogLog -Value ("{0} phasea-watchdog error {1}" -f [DateTime]::UtcNow.ToString('o'), $_.Exception.Message)
    }

    Start-Sleep -Seconds $intervalSeconds
}

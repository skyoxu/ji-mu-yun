$ErrorActionPreference = 'Stop'

$appUrl = 'http://127.0.0.1:18080/healthz'
$publicUrl = 'http://47.250.131.70:8080/healthz'
$repositoryRoot = 'C:\jimuyun'
$startScript = 'C:\jimuyun\runtime\phase-a\start-phasea.ps1'
$pidFile = 'C:\jimuyun\logs\phase-a-innernet\phasea.pid'
$runtimeLogRoot = 'C:\jimuyun\logs\phase-a-innernet\runtime'
$eventLog = Join-Path $runtimeLogRoot 'phasea-ensure.jsonl'
$timeoutSeconds = 45

New-Item -ItemType Directory -Force -Path $runtimeLogRoot | Out-Null

function Write-EnsureEvent {
    param(
        [string]$Status,
        [string]$Action,
        [string]$Message
    )

    $payload = [ordered]@{
        timestamp_utc = [DateTime]::UtcNow.ToString('o')
        status = $Status
        action = $Action
        message = $Message
    }
    ($payload | ConvertTo-Json -Compress) + [Environment]::NewLine | Out-File -FilePath $eventLog -Encoding utf8 -Append
    Write-Output ($payload | ConvertTo-Json -Compress)
}

function Test-HttpHealthy {
    param(
        [string]$Url,
        [int]$TimeoutSec = 5
    )

    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec $TimeoutSec
        if ($response.StatusCode -eq 200 -and $response.Content -match '"status"\s*:\s*"ok"') {
            return $true
        }
    }
    catch {
        return $false
    }

    return $false
}

function Stop-StalePhaseAProcess {
    if (!(Test-Path $pidFile)) {
        return $false
    }

    $pidText = (Get-Content -Path $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
    if ([string]::IsNullOrWhiteSpace($pidText)) {
        return $false
    }

    $existing = Get-Process -Id ([int]$pidText) -ErrorAction SilentlyContinue
    if ($null -eq $existing) {
        return $false
    }

    Stop-Process -Id $existing.Id -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    return $true
}

if (Test-HttpHealthy -Url $appUrl) {
    $publicHealthy = Test-HttpHealthy -Url $publicUrl
    if ($publicHealthy) {
        Write-EnsureEvent -Status 'ok' -Action 'noop' -Message 'Phase A local and public health are already healthy.'
        exit 0
    }

    Write-EnsureEvent -Status 'warn' -Action 'noop' -Message 'Phase A local health is healthy but public proxy health is still failing.'
    exit 0
}

$stopped = Stop-StalePhaseAProcess
if ($stopped) {
    Write-EnsureEvent -Status 'info' -Action 'stop-stale' -Message 'Stopped stale PhaseA process from pid file before restart.'
}

if (!(Test-Path $startScript)) {
    Write-EnsureEvent -Status 'fail' -Action 'start-missing' -Message "Start script missing: $startScript"
    exit 1
}

& $startScript

$deadline = (Get-Date).AddSeconds($timeoutSeconds)
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 2
    if (Test-HttpHealthy -Url $appUrl) {
        $publicHealthy = Test-HttpHealthy -Url $publicUrl
        if ($publicHealthy) {
            Write-EnsureEvent -Status 'ok' -Action 'restart' -Message 'Phase A local and public health recovered after restart.'
            exit 0
        }

        Write-EnsureEvent -Status 'warn' -Action 'restart' -Message 'Phase A local health recovered after restart but public proxy health is still failing.'
        exit 0
    }
}

Write-EnsureEvent -Status 'fail' -Action 'restart-timeout' -Message 'Phase A did not recover local health within the timeout window.'
exit 1

$env:APP_BIND_URL = 'http://127.0.0.1:18080'
$env:HTTPS_TERMINATION = 'caddy'
$env:PUBLIC_BASE_URL = 'https://47.250.131.70:8080'
$env:HOSTED_WORKSPACE_ROOT = 'C:\jimuyun\logs\phase-a-innernet\workspaces'
$env:HOSTED_PROJECT_LIMIT = '2'
$env:PHASEA_METADATA_DB_PATH = 'C:\jimuyun\logs\phase-a-innernet\data\phase-a-platform.sqlite3'
$env:PHASEA_REPOSITORY_ROOT = 'C:\jimuyun'
$env:PHASEA_CODEX_COMMAND = 'C:\Windows\System32\config\systemprofile\AppData\Roaming\npm\codex.cmd'
Remove-Item Env:\PHASEA_CHAT_TEST_MODE -ErrorAction SilentlyContinue
Remove-Item Env:\PHASEA_CHAT_BACKEND -ErrorAction SilentlyContinue
$env:GODOT_BIN = 'C:\Godot\4.5.1-mono\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64_console.exe'
Set-Location 'C:\jimuyun'
$runtimeRoot = 'C:\jimuyun\logs\phase-a-innernet\runtime'
$tempRoot = 'C:\jimuyun\logs\phase-a-innernet\tmp'
$buildRoot = 'C:\Users\Administrator\.codex\memories\phasea-runtime-build'
$objRoot = Join-Path $buildRoot 'obj'
$outRoot = Join-Path $buildRoot 'out'
$pidFile = 'C:\jimuyun\logs\phase-a-innernet\phasea.pid'
$dotnet = 'C:\Program Files\dotnet\dotnet.exe'
$repoRootNormalized = 'C:/jimuyun'
$ripgrepDir = 'C:\Windows\System32\config\systemprofile\AppData\Roaming\npm\node_modules\@openai\codex\node_modules\@openai\codex-win32-x64\vendor\x86_64-pc-windows-msvc\path'

New-Item -ItemType Directory -Force -Path $runtimeRoot, $tempRoot, $buildRoot, $objRoot, $outRoot | Out-Null
Remove-Item -LiteralPath $objRoot, $outRoot -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $objRoot, $outRoot | Out-Null

if ([string]::IsNullOrWhiteSpace($env:PHASEA_ADMIN_TOKEN_HASH)) {
  $machineHash = [System.Environment]::GetEnvironmentVariable('PHASEA_ADMIN_TOKEN_HASH', 'Machine')
  $userHash = [System.Environment]::GetEnvironmentVariable('PHASEA_ADMIN_TOKEN_HASH', 'User')
  $processHash = [System.Environment]::GetEnvironmentVariable('PHASEA_ADMIN_TOKEN_HASH', 'Process')
  $resolvedHash = $processHash
  if ([string]::IsNullOrWhiteSpace($resolvedHash)) { $resolvedHash = $userHash }
  if ([string]::IsNullOrWhiteSpace($resolvedHash)) { $resolvedHash = $machineHash }
  if ([string]::IsNullOrWhiteSpace($resolvedHash)) {
    throw "phasea_admin_token_hash_missing"
  }
  $env:PHASEA_ADMIN_TOKEN_HASH = $resolvedHash
}

if (Test-Path $ripgrepDir) {
  if (($env:PATH -split ';') -notcontains $ripgrepDir) {
    $env:PATH = "$ripgrepDir;$env:PATH"
  }
}

& git config --global --add safe.directory $repoRootNormalized 2>$null

if (Test-Path $pidFile) {
  $oldPidText = Get-Content -LiteralPath $pidFile -Raw -ErrorAction SilentlyContinue
  if ($null -eq $oldPidText) { $oldPidText = '' }
  $oldPid = 0
  if ([int]::TryParse($oldPidText.Trim(), [ref]$oldPid)) {
    $oldProcess = Get-Process -Id $oldPid -ErrorAction SilentlyContinue
    if ($oldProcess -and $oldProcess.ProcessName -eq 'PhaseA.Platform') {
      Stop-Process -Id $oldPid -Force -ErrorAction SilentlyContinue
      Wait-Process -Id $oldPid -Timeout 10 -ErrorAction SilentlyContinue
    }
  }
}

& $dotnet build 'PhaseA.Platform\PhaseA.Platform.csproj' `
  -c Debug `
  "-p:OutDir=$outRoot\" `
  /nologo

if ($LASTEXITCODE -ne 0) {
  throw "phasea_build_failed"
}

$exePath = Join-Path $outRoot 'PhaseA.Platform.exe'
if (!(Test-Path $exePath)) {
  throw "phasea_exe_missing"
}

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $exePath
$psi.WorkingDirectory = 'C:\jimuyun'
$psi.UseShellExecute = $false
$psi.CreateNoWindow = $true

foreach ($key in [System.Environment]::GetEnvironmentVariables().Keys) {
  $psi.Environment[$key] = [string][System.Environment]::GetEnvironmentVariable([string]$key)
}

$psi.Environment['APP_BIND_URL'] = $env:APP_BIND_URL
$psi.Environment['ASPNETCORE_URLS'] = $env:APP_BIND_URL
$psi.Environment['HTTPS_TERMINATION'] = $env:HTTPS_TERMINATION
$psi.Environment['PUBLIC_BASE_URL'] = $env:PUBLIC_BASE_URL
$psi.Environment['HOSTED_WORKSPACE_ROOT'] = $env:HOSTED_WORKSPACE_ROOT
$psi.Environment['HOSTED_PROJECT_LIMIT'] = $env:HOSTED_PROJECT_LIMIT
$psi.Environment['PHASEA_METADATA_DB_PATH'] = $env:PHASEA_METADATA_DB_PATH
$psi.Environment['PHASEA_REPOSITORY_ROOT'] = $env:PHASEA_REPOSITORY_ROOT
$psi.Environment['PHASEA_ADMIN_TOKEN_HASH'] = $env:PHASEA_ADMIN_TOKEN_HASH
$psi.Environment['PHASEA_CODEX_COMMAND'] = $env:PHASEA_CODEX_COMMAND
$psi.Environment['GODOT_BIN'] = $env:GODOT_BIN
$psi.Environment['PATH'] = $env:PATH
$psi.Environment['TEMP'] = $tempRoot
$psi.Environment['TMP'] = $tempRoot

$process = [System.Diagnostics.Process]::Start($psi)

Set-Content -Path $pidFile -Value $process.Id -Encoding ascii

$env:APP_BIND_URL = 'http://127.0.0.1:18080'
$env:HTTPS_TERMINATION = 'caddy'
$env:PUBLIC_BASE_URL = 'https://47.86.160.138:8080'
$env:HOSTED_WORKSPACE_ROOT = 'C:\jimuyun\logs\phase-a-innernet\workspaces'
$env:HOSTED_PROJECT_LIMIT = '2'
if ([string]::IsNullOrWhiteSpace($env:PHASEA_MAX_CONCURRENT_CHATS)) { $env:PHASEA_MAX_CONCURRENT_CHATS = '8' }
if ([string]::IsNullOrWhiteSpace($env:PHASEA_MAX_CONCURRENT_CHATS_PER_ACCOUNT)) { $env:PHASEA_MAX_CONCURRENT_CHATS_PER_ACCOUNT = '2' }
if ([string]::IsNullOrWhiteSpace($env:PHASEA_MAX_CONCURRENT_PROJECT_CREATIONS)) { $env:PHASEA_MAX_CONCURRENT_PROJECT_CREATIONS = '3' }
if ([string]::IsNullOrWhiteSpace($env:PHASEA_MAX_CONCURRENT_PROJECT_CREATIONS_PER_ACCOUNT)) { $env:PHASEA_MAX_CONCURRENT_PROJECT_CREATIONS_PER_ACCOUNT = '1' }
if ([string]::IsNullOrWhiteSpace($env:PHASEA_MAX_CONCURRENT_OTHER_RUNS)) { $env:PHASEA_MAX_CONCURRENT_OTHER_RUNS = '1' }
$env:PHASEA_METADATA_DB_PATH = 'C:\jimuyun\logs\phase-a-innernet\data\phase-a-platform.sqlite3'
$env:PHASEA_REPOSITORY_ROOT = 'C:\jimuyun'
$preferredCodexCommands = @(
  'C:\Users\Administrator\AppData\Roaming\npm\codex.cmd',
  'C:\Windows\System32\config\systemprofile\AppData\Roaming\npm\codex.cmd'
)
$env:PHASEA_CODEX_COMMAND = ($preferredCodexCommands | Where-Object { Test-Path $_ } | Select-Object -First 1)
if ([string]::IsNullOrWhiteSpace($env:PHASEA_CODEX_COMMAND)) {
  $env:PHASEA_CODEX_COMMAND = 'codex'
}
Remove-Item Env:\PHASEA_CHAT_TEST_MODE -ErrorAction SilentlyContinue
Remove-Item Env:\PHASEA_CHAT_BACKEND -ErrorAction SilentlyContinue
$env:GODOT_BIN = 'C:\Godot\4.5.1-mono\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64_console.exe'
$env:DOTNET_ROOT = 'C:\jimuyun\.dotnet'
Set-Location 'C:\jimuyun'
$runtimeRoot = 'C:\jimuyun\logs\phase-a-innernet\runtime'
$tempRoot = 'C:\jimuyun\logs\phase-a-innernet\tmp'
$buildRoot = 'C:\Users\Administrator\.codex\memories\phasea-runtime-build'
$objRoot = Join-Path $buildRoot 'obj'
$outRoot = Join-Path $buildRoot 'out'
$pidFile = 'C:\jimuyun\logs\phase-a-innernet\phasea.pid'
$dotnet = 'C:\Program Files\dotnet\dotnet.exe'
$repoDotnet = 'C:\jimuyun\.dotnet\dotnet.exe'
$repoRootNormalized = 'C:/jimuyun'
$ripgrepDir = 'C:\Windows\System32\config\systemprofile\AppData\Roaming\npm\node_modules\@openai\codex\node_modules\@openai\codex-win32-x64\vendor\x86_64-pc-windows-msvc\path'

New-Item -ItemType Directory -Force -Path $runtimeRoot, $tempRoot, $buildRoot, $objRoot, $outRoot | Out-Null
Remove-Item -LiteralPath $objRoot, $outRoot -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $objRoot, $outRoot | Out-Null

if (!(Test-Path $dotnet) -and (Test-Path $repoDotnet)) {
  $dotnet = $repoDotnet
}

function Resolve-HostEnvironmentValue {
  param([string]$Name)
  $processValue = [System.Environment]::GetEnvironmentVariable($Name, 'Process')
  $userValue = [System.Environment]::GetEnvironmentVariable($Name, 'User')
  $machineValue = [System.Environment]::GetEnvironmentVariable($Name, 'Machine')
  $resolvedValue = $processValue
  if ([string]::IsNullOrWhiteSpace($resolvedValue)) { $resolvedValue = $userValue }
  if ([string]::IsNullOrWhiteSpace($resolvedValue)) { $resolvedValue = $machineValue }
  return $resolvedValue
}

if ([string]::IsNullOrWhiteSpace($env:PHASEA_ADMIN_TOKEN_HASH)) {
  $resolvedHash = Resolve-HostEnvironmentValue 'PHASEA_ADMIN_TOKEN_HASH'
  if ([string]::IsNullOrWhiteSpace($resolvedHash)) {
    throw "phasea_admin_token_hash_missing"
  }
  $env:PHASEA_ADMIN_TOKEN_HASH = $resolvedHash
}

foreach ($concurrencyName in @(
  'PHASEA_MAX_CONCURRENT_CHATS',
  'PHASEA_MAX_CONCURRENT_CHATS_PER_ACCOUNT',
  'PHASEA_MAX_CONCURRENT_PROJECT_CREATIONS',
  'PHASEA_MAX_CONCURRENT_PROJECT_CREATIONS_PER_ACCOUNT',
  'PHASEA_MAX_CONCURRENT_OTHER_RUNS'
)) {
  $hostValue = [System.Environment]::GetEnvironmentVariable($concurrencyName, 'User')
  if ([string]::IsNullOrWhiteSpace($hostValue)) {
    $hostValue = [System.Environment]::GetEnvironmentVariable($concurrencyName, 'Machine')
  }
  if (![string]::IsNullOrWhiteSpace($hostValue)) {
    [System.Environment]::SetEnvironmentVariable($concurrencyName, $hostValue, 'Process')
  }
}

$aiCodeMirrorCookie = Resolve-HostEnvironmentValue 'AICODEMIRROR_COOKIE'
$aiCodeMirrorBaseUrl = Resolve-HostEnvironmentValue 'AICODEMIRROR_BASE_URL'
$aiCodeMirrorBillingEnabled = Resolve-HostEnvironmentValue 'AICODEMIRROR_BILLING_ENABLED'
$aiCodeMirrorApiKeyName = Resolve-HostEnvironmentValue 'AICODEMIRROR_API_KEY_NAME'
$aiCodeMirrorCodexHomeRoot = Resolve-HostEnvironmentValue 'AICODEMIRROR_CODEX_HOME_ROOT'
if (![string]::IsNullOrWhiteSpace($aiCodeMirrorCookie)) {
  $env:AICODEMIRROR_COOKIE = $aiCodeMirrorCookie
  if ([string]::IsNullOrWhiteSpace($aiCodeMirrorBillingEnabled)) {
    $aiCodeMirrorBillingEnabled = 'true'
  }
}
if (![string]::IsNullOrWhiteSpace($aiCodeMirrorBaseUrl)) { $env:AICODEMIRROR_BASE_URL = $aiCodeMirrorBaseUrl }
if (![string]::IsNullOrWhiteSpace($aiCodeMirrorBillingEnabled)) { $env:AICODEMIRROR_BILLING_ENABLED = $aiCodeMirrorBillingEnabled }
if (![string]::IsNullOrWhiteSpace($aiCodeMirrorApiKeyName)) { $env:AICODEMIRROR_API_KEY_NAME = $aiCodeMirrorApiKeyName }
if (![string]::IsNullOrWhiteSpace($aiCodeMirrorCodexHomeRoot)) { $env:AICODEMIRROR_CODEX_HOME_ROOT = $aiCodeMirrorCodexHomeRoot }

if (Test-Path $ripgrepDir) {
  $env:PHASEA_RIPGREP_DIR = $ripgrepDir
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
$psi.Environment['PHASEA_MAX_CONCURRENT_CHATS'] = $env:PHASEA_MAX_CONCURRENT_CHATS
$psi.Environment['PHASEA_MAX_CONCURRENT_CHATS_PER_ACCOUNT'] = $env:PHASEA_MAX_CONCURRENT_CHATS_PER_ACCOUNT
$psi.Environment['PHASEA_MAX_CONCURRENT_PROJECT_CREATIONS'] = $env:PHASEA_MAX_CONCURRENT_PROJECT_CREATIONS
$psi.Environment['PHASEA_MAX_CONCURRENT_PROJECT_CREATIONS_PER_ACCOUNT'] = $env:PHASEA_MAX_CONCURRENT_PROJECT_CREATIONS_PER_ACCOUNT
$psi.Environment['PHASEA_MAX_CONCURRENT_OTHER_RUNS'] = $env:PHASEA_MAX_CONCURRENT_OTHER_RUNS
$psi.Environment['PHASEA_METADATA_DB_PATH'] = $env:PHASEA_METADATA_DB_PATH
$psi.Environment['PHASEA_REPOSITORY_ROOT'] = $env:PHASEA_REPOSITORY_ROOT
$psi.Environment['PHASEA_ADMIN_TOKEN_HASH'] = $env:PHASEA_ADMIN_TOKEN_HASH
$psi.Environment['PHASEA_CODEX_COMMAND'] = $env:PHASEA_CODEX_COMMAND
$psi.Environment['PHASEA_RIPGREP_DIR'] = $env:PHASEA_RIPGREP_DIR
$psi.Environment['GODOT_BIN'] = $env:GODOT_BIN
$psi.Environment['DOTNET_ROOT'] = $env:DOTNET_ROOT
if (![string]::IsNullOrWhiteSpace($env:AICODEMIRROR_BILLING_ENABLED)) { $psi.Environment['AICODEMIRROR_BILLING_ENABLED'] = $env:AICODEMIRROR_BILLING_ENABLED }
if (![string]::IsNullOrWhiteSpace($env:AICODEMIRROR_BASE_URL)) { $psi.Environment['AICODEMIRROR_BASE_URL'] = $env:AICODEMIRROR_BASE_URL }
if (![string]::IsNullOrWhiteSpace($env:AICODEMIRROR_COOKIE)) { $psi.Environment['AICODEMIRROR_COOKIE'] = $env:AICODEMIRROR_COOKIE }
if (![string]::IsNullOrWhiteSpace($env:AICODEMIRROR_API_KEY_NAME)) { $psi.Environment['AICODEMIRROR_API_KEY_NAME'] = $env:AICODEMIRROR_API_KEY_NAME }
if (![string]::IsNullOrWhiteSpace($env:AICODEMIRROR_CODEX_HOME_ROOT)) { $psi.Environment['AICODEMIRROR_CODEX_HOME_ROOT'] = $env:AICODEMIRROR_CODEX_HOME_ROOT }
$psi.Environment['PATH'] = $env:PATH
$psi.Environment['TEMP'] = $tempRoot
$psi.Environment['TMP'] = $tempRoot

$process = [System.Diagnostics.Process]::Start($psi)

Set-Content -Path $pidFile -Value $process.Id -Encoding ascii

[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimeRoot = Join-Path $projectRoot 'data\output\week7_runtime'
$archiveRoot = Join-Path $projectRoot 'data\output\week7_service'
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
$nodeExe = (Get-Command node -ErrorAction Stop).Source
$viteScript = Join-Path $projectRoot 'gui-prototype\node_modules\vite\bin\vite.js'
if (!(Test-Path -LiteralPath $pythonExe) -or !(Test-Path -LiteralPath $viteScript)) {
    throw 'The project Python environment and installed GUI dependencies are required.'
}
foreach ($port in @(8766, 5177)) {
    $listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($listener) { throw "Port $port is already in use. Existing processes were left running." }
}
$null = New-Item -ItemType Directory -Force -Path $runtimeRoot
$runTag = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
$launched = @()
$oldMode = $env:VITE_INSPECTION_MODE
$oldApi = $env:VITE_WEEK7_API_URL
$oldProfile = $env:VITE_OFFLINE_PROFILE
try {
    $api = Start-Process -FilePath $pythonExe -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru `
        -ArgumentList "-m src.week7_service --output `"$archiveRoot`" --port 8766" `
        -RedirectStandardOutput (Join-Path $runtimeRoot "$runTag-api.log") `
        -RedirectStandardError (Join-Path $runtimeRoot "$runTag-api.err.log")
    $launched += $api
    $env:VITE_INSPECTION_MODE = 'week7'
    $env:VITE_WEEK7_API_URL = 'http://127.0.0.1:8766'
    $env:VITE_OFFLINE_PROFILE = 'plan_a'
    $gui = Start-Process -FilePath $nodeExe -WorkingDirectory (Join-Path $projectRoot 'gui-prototype') `
        -WindowStyle Hidden -PassThru -ArgumentList "`"$viteScript`" --host 127.0.0.1 --port 5177 --strictPort" `
        -RedirectStandardOutput (Join-Path $runtimeRoot "$runTag-gui.log") `
        -RedirectStandardError (Join-Path $runtimeRoot "$runTag-gui.err.log")
    $launched += $gui
    $ready = $false
    $lastProbeError = ''
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        if ($api.HasExited -or $gui.HasExited) { throw "A service stopped. See $runtimeRoot" }
        try {
            $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8766/api/week7/health' -TimeoutSec 1
            $page = Invoke-WebRequest -Uri 'http://127.0.0.1:5177' -UseBasicParsing -TimeoutSec 1
            if ($health.mode -eq 'plan_a_offline' -and $page.StatusCode -eq 200) { $ready = $true; break }
        } catch {
            $lastProbeError = $_.Exception.Message
            Start-Sleep -Milliseconds 200
        }
    }
    if (!$ready) { throw "Offline capture services did not become ready: $lastProbeError. See $runtimeRoot" }
    $state = @($launched | ForEach-Object {
        @{ process_id = $_.Id; started_ticks = $_.StartTime.ToUniversalTime().Ticks.ToString() }
    })
    ConvertTo-Json -InputObject $state | Set-Content -LiteralPath (Join-Path $runtimeRoot 'processes.json') -Encoding UTF8
    Write-Output 'Plan A offline capture: http://127.0.0.1:5177'
    Write-Output "Archive: $archiveRoot"
} catch {
    foreach ($process in $launched) {
        if (!$process.HasExited) { Stop-Process -Id $process.Id -ErrorAction SilentlyContinue }
    }
    throw
} finally {
    $env:VITE_INSPECTION_MODE = $oldMode
    $env:VITE_WEEK7_API_URL = $oldApi
    $env:VITE_OFFLINE_PROFILE = $oldProfile
}

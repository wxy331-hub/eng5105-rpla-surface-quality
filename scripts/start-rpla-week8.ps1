[CmdletBinding()]
param(
    [string]$CameraDevice = '',
    [ValidateSet('auto', 'dshow', 'msmf', 'v4l2')]
    [string]$CameraBackend = '',
    [string]$Resolution = '',
    [switch]$CheckConfig,
    [switch]$WaitForCamera,
    [switch]$Demo,
    [switch]$NoBrowser
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimeRoot = Join-Path $projectRoot 'data\output\week8_runtime'
$archiveRoot = Join-Path $projectRoot 'data\output\week8_service'
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'

if ($Demo) {
    # This laptop's external USB camera was identified at DirectShow index 1.
    # Never fall back to index 0: it is the integrated laptop camera.
    if (!$CameraDevice) { $CameraDevice = '1' }
    if (!$CameraBackend) { $CameraBackend = 'dshow' }
    if (!$Resolution) { $Resolution = 'UHD' }
    $archiveRoot = Join-Path $projectRoot 'data\output\camera_demo'
}

# Reuse the existing validated USB mode selection without opening a camera.
$selection = @{ SourceType = 'usb_uvc'; CheckConfig = $true }
if ($CameraDevice) { $selection.CameraDevice = $CameraDevice }
if ($CameraBackend) { $selection.CameraBackend = $CameraBackend }
if ($Resolution) { $selection.Resolution = $Resolution }
$plan = (& (Join-Path $PSScriptRoot 'start-rpla-live.ps1') @selection) | ConvertFrom-Json
if ($CheckConfig) {
    $plan | Add-Member -NotePropertyName sample_archive -NotePropertyValue $archiveRoot
    $plan | Add-Member -NotePropertyName sample_service -NotePropertyValue 'http://127.0.0.1:8765/api/week7'
    $plan | Add-Member -NotePropertyName gui_url -NotePropertyValue 'http://127.0.0.1:5177'
    $plan | Add-Member -NotePropertyName demo_mode -NotePropertyValue ([bool]$Demo)
    $plan | ConvertTo-Json -Depth 8
    return
}

$nodeExe = (Get-Command node -ErrorAction Stop).Source
$viteScript = Join-Path $projectRoot 'gui-prototype\node_modules\vite\bin\vite.js'
if (!(Test-Path -LiteralPath $pythonExe) -or !(Test-Path -LiteralPath $viteScript)) {
    throw 'The project Python environment and installed GUI dependencies are required.'
}
foreach ($port in @(8765, 5177)) {
    if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
        throw "Port $port is in use. Stop its owning project launcher before starting camera capture. Existing processes were left running."
    }
}
$null = New-Item -ItemType Directory -Force -Path $runtimeRoot
$runTag = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
$environmentNames = @('RPLA_SOURCE_TYPE', 'RPLA_CONFIG_PATH', 'RPLA_CAMERA_DEVICE',
    'RPLA_CAMERA_BACKEND', 'RPLA_RESOLUTION', 'RPLA_CAMERA_IP', 'RPLA_STREAM_URL',
    'RPLA_CONTROL_URL', 'RPLA_FRAMESIZE', 'RPLA_CORS_ORIGINS',
    'VITE_INSPECTION_MODE', 'VITE_INSPECTION_API_URL', 'VITE_INSPECTION_WS_URL',
    'VITE_SAMPLE_API_URL', 'VITE_WEEK7_API_URL', 'VITE_CAMERA_STREAM_URL')
$previousEnvironment = @{}
foreach ($name in $environmentNames) {
    $previousEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}
$launched = @()
try {
    $env:RPLA_SOURCE_TYPE = 'usb_uvc'
    $env:RPLA_CONFIG_PATH = Join-Path $projectRoot 'config\live_service.json'
    $env:RPLA_CAMERA_DEVICE = [string]$plan.connection.device
    $env:RPLA_CAMERA_BACKEND = [string]$plan.connection.backend
    $env:RPLA_RESOLUTION = [string]$plan.resolution
    $env:RPLA_CORS_ORIGINS = 'http://127.0.0.1:5177,http://localhost:5177,http://127.0.0.1:5173,http://localhost:5173'
    foreach ($name in @('RPLA_CAMERA_IP', 'RPLA_STREAM_URL', 'RPLA_CONTROL_URL', 'RPLA_FRAMESIZE')) {
        [Environment]::SetEnvironmentVariable($name, $null, 'Process')
    }
    $cameraStartOption = if ($WaitForCamera) { ' --wait-for-camera' } else { '' }
    $api = Start-Process -FilePath $pythonExe -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru `
        -ArgumentList "-m src.week8_service --output `"$archiveRoot`" --port 8765$cameraStartOption" `
        -RedirectStandardOutput (Join-Path $runtimeRoot "$runTag-api.log") `
        -RedirectStandardError (Join-Path $runtimeRoot "$runTag-api.err.log")
    $launched += $api
    $env:VITE_INSPECTION_MODE = 'service'
    $env:VITE_INSPECTION_API_URL = 'http://127.0.0.1:8765'
    $env:VITE_INSPECTION_WS_URL = 'ws://127.0.0.1:8765/ws'
    $env:VITE_SAMPLE_API_URL = 'http://127.0.0.1:8765'
    $env:VITE_WEEK7_API_URL = 'http://127.0.0.1:8765'
    $env:VITE_CAMERA_STREAM_URL = $null
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
            $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/api/week7/health' -TimeoutSec 1
            $page = Invoke-WebRequest -Uri 'http://127.0.0.1:5177' -UseBasicParsing -TimeoutSec 1
            # Service readiness is independent of whether hardware has arrived.
            if ($health.mode -eq 'plan_a_camera' -and $page.StatusCode -eq 200) { $ready = $true; break }
            $lastProbeError = 'Unexpected service mode'
        } catch { $lastProbeError = $_.Exception.Message }
        Start-Sleep -Milliseconds 200
    }
    if (!$ready) { throw "Camera services did not become ready: $lastProbeError. See $runtimeRoot" }
    # A Windows venv python.exe may delegate to a child interpreter. Record the
    # verified listener too, so stopping its parent cannot leave the camera open.
    $ownedListeners = @()
    foreach ($port in @(8765, 5177)) {
        foreach ($listener in @(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)) {
            if ($listener.OwningProcess -notin @($launched.Id)) {
                $child = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
                if ($child.ParentProcessId -notin @($launched.Id)) {
                    throw "Port $port belongs to an unexpected process; no ownership was assumed."
                }
                $ownedListeners += Get-Process -Id $listener.OwningProcess
            }
        }
    }
    $state = @(@($ownedListeners) + @($launched) | ForEach-Object {
        @{ process_id = $_.Id; started_ticks = $_.StartTime.ToUniversalTime().Ticks.ToString() }
    })
    ConvertTo-Json -InputObject $state | Set-Content -LiteralPath (Join-Path $runtimeRoot 'processes.json') -Encoding UTF8
    if ($Demo) { Write-Output 'Camera demo: http://127.0.0.1:5177/' }
    else { Write-Output 'Plan A camera capture: http://127.0.0.1:5177/#sample-capture' }
    Write-Output "Camera state: $($health.camera.status). Requested mode: $($plan.resolution)."
    Write-Output "Archive: $archiveRoot"
} catch {
    foreach ($process in $launched) {
        if (!$process.HasExited) { Stop-Process -Id $process.Id -ErrorAction SilentlyContinue }
    }
    throw
} finally {
    foreach ($name in $environmentNames) {
        [Environment]::SetEnvironmentVariable($name, $previousEnvironment[$name], 'Process')
    }
}
if ($Demo -and !$NoBrowser) {
    # Opening the operator's browser is separate from service ownership: a
    # browser failure must not tear down a working camera/GUI pair.
    try { Start-Process -FilePath 'http://127.0.0.1:5177/' }
    catch { Write-Warning 'Services are running. Open http://127.0.0.1:5177/ in your browser.' }
}

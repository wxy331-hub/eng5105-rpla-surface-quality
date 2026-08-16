param(
    [string]$CameraIp = "172.20.10.2",
    [ValidateSet("VGA", "SVGA", "XGA", "SXGA", "UXGA", "QXGA")]
    [string]$Resolution = "SVGA",
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$guiRoot = Join-Path $projectRoot "gui-prototype"
$runtimeRoot = Join-Path $projectRoot "data\output\live_service"
$backendLog = Join-Path $runtimeRoot "backend.stdout.log"
$backendErrorLog = Join-Path $runtimeRoot "backend.stderr.log"
$guiLog = Join-Path $runtimeRoot "gui.stdout.log"
$guiErrorLog = Join-Path $runtimeRoot "gui.stderr.log"
$serviceConfigPath = Join-Path $projectRoot "config\live_service.json"
$Resolution = $Resolution.ToUpperInvariant()

if (-not (Test-Path -LiteralPath $python)) {
    throw "Python virtual environment is missing: $python"
}
if (-not (Test-Path -LiteralPath $guiRoot)) {
    throw "GUI project is missing: $guiRoot"
}
if (-not (Test-Path -LiteralPath $serviceConfigPath)) {
    throw "Live service configuration is missing: $serviceConfigPath"
}

$serviceConfig = Get-Content -Raw -Encoding utf8 $serviceConfigPath | ConvertFrom-Json
$resolutionProfile = $serviceConfig.resolution_profiles.PSObject.Properties[$Resolution].Value
if (-not $resolutionProfile) {
    throw "Resolution profile is missing from live_service.json: $Resolution"
}
$frameSizeValue = [int]$resolutionProfile.framesize_control_value
$resolutionWidth = [int]$resolutionProfile.width_px
$resolutionHeight = [int]$resolutionProfile.height_px

New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null

function Stop-ProjectListener {
    param([int]$Port)
    $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    foreach ($connection in $connections) {
        $process = Get-CimInstance Win32_Process -Filter "ProcessId = $($connection.OwningProcess)" -ErrorAction SilentlyContinue
        if ($process.CommandLine -and $process.CommandLine.Contains($projectRoot)) {
            Stop-Process -Id $connection.OwningProcess -Force
        } elseif ($process) {
            throw "Port $Port is occupied by a process outside this project: $($process.Name)"
        }
    }
}

function Wait-Http {
    param([string]$Url, [int]$TimeoutSeconds = 25)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 2
            if ($response.StatusCode -eq 200) { return }
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }
    throw "Timed out waiting for $Url"
}

function Wait-CameraFrame {
    param([int]$TimeoutSeconds = 30)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/health" -TimeoutSec 2
            if ($health.camera_configured -and [int]$health.frames_received -gt 0) { return }
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }
    throw "The Python service started, but no camera frame arrived within $TimeoutSeconds seconds. Close any ESP32 CameraWebServer preview and try again."
}

function Find-NodeExecutable {
    $systemNode = Get-Command node.exe -ErrorAction SilentlyContinue
    if ($systemNode) { return $systemNode.Source }

    $codexNode = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"
    if (Test-Path -LiteralPath $codexNode) { return $codexNode }

    throw "Node.js is required to start the GUI. Install Node.js 20 or later, then run START_RPLA_LIVE.cmd again."
}

Stop-ProjectListener -Port 8765
Stop-ProjectListener -Port 5173
Start-Sleep -Seconds 1

$otherCameraClients = Get-NetTCPConnection -RemoteAddress $CameraIp -RemotePort 81 -State Established -ErrorAction SilentlyContinue
if ($otherCameraClients) {
    throw "The ESP32 stream is already in use. Stop the CameraWebServer preview or another direct camera client, then run this script again."
}

$controlUrl = "http://$CameraIp/control?var=framesize&val=$frameSizeValue"
$statusUrl = "http://$CameraIp/status"
Invoke-WebRequest -UseBasicParsing -Uri $controlUrl -TimeoutSec 8 | Out-Null
$cameraStatus = Invoke-RestMethod -Uri $statusUrl -TimeoutSec 8
if ([int]$cameraStatus.framesize -ne $frameSizeValue) {
    throw "The camera did not accept $Resolution framesize $frameSizeValue."
}

$env:RPLA_CAMERA_IP = $CameraIp
$env:RPLA_STREAM_URL = "http://${CameraIp}:81/stream"
$env:RPLA_CONTROL_URL = "http://$CameraIp"
$env:RPLA_RESOLUTION = $Resolution
$env:RPLA_FRAMESIZE = [string]$frameSizeValue

Start-Process -FilePath $python `
    -ArgumentList @("-m", "uvicorn", "src.live_service:app", "--app-dir", $projectRoot, "--host", "127.0.0.1", "--port", "8765") `
    -WorkingDirectory $projectRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput $backendLog `
    -RedirectStandardError $backendErrorLog | Out-Null

Wait-Http -Url "http://127.0.0.1:8765/api/health"
Wait-CameraFrame

$node = Find-NodeExecutable
$viteEntry = Join-Path $guiRoot "node_modules\vite\bin\vite.js"
if (-not (Test-Path -LiteralPath $viteEntry)) {
    throw "GUI dependencies are missing: $viteEntry"
}
Start-Process -FilePath $node `
    -ArgumentList @($viteEntry, "--mode", "live", "--host", "127.0.0.1", "--port", "5173") `
    -WorkingDirectory $guiRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput $guiLog `
    -RedirectStandardError $guiErrorLog | Out-Null

Wait-Http -Url "http://127.0.0.1:5173/"

$backendPid = (Get-NetTCPConnection -LocalPort 8765 -State Listen | Select-Object -First 1).OwningProcess
$guiPid = (Get-NetTCPConnection -LocalPort 5173 -State Listen | Select-Object -First 1).OwningProcess
Set-Content -LiteralPath (Join-Path $runtimeRoot "backend.pid") -Value $backendPid -Encoding ascii
Set-Content -LiteralPath (Join-Path $runtimeRoot "gui.pid") -Value $guiPid -Encoding ascii

Write-Host "rPLA live inspection is ready." -ForegroundColor Green
Write-Host "Camera: $Resolution ${resolutionWidth}x${resolutionHeight} at $CameraIp"
Write-Host "API:    http://127.0.0.1:8765/api/health"
Write-Host "GUI:    http://127.0.0.1:5173/"
Write-Host "Logs:   $runtimeRoot"

if (-not $NoBrowser) {
    Start-Process "http://127.0.0.1:5173/"
}

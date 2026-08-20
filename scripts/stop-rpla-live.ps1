$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$runtimeRoot = Join-Path $projectRoot "data\output\live_service"

foreach ($port in 5173, 8765) {
    $connections = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    foreach ($connection in $connections) {
        $process = Get-CimInstance Win32_Process -Filter "ProcessId = $($connection.OwningProcess)" -ErrorAction SilentlyContinue
        if ($process.CommandLine -and $process.CommandLine.Contains($projectRoot)) {
            Stop-Process -Id $connection.OwningProcess -Force
            Write-Host "Stopped project process on port $port (PID $($connection.OwningProcess))."
        }
    }
}

# A backend that failed to claim port 8765 keeps running without listening, so the
# port sweep above cannot see it. It still holds the single MJPEG connection the
# ESP32 allows, which starves the next run and corrupts any throughput measurement.
$stragglers = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue |
    Where-Object {
        $_.CommandLine -and
        $_.CommandLine.Contains($projectRoot) -and
        $_.CommandLine.Contains("live_service")
    }
foreach ($straggler in $stragglers) {
    Stop-Process -Id $straggler.ProcessId -Force -ErrorAction SilentlyContinue
    Write-Host "Stopped orphaned backend process (PID $($straggler.ProcessId))."
}

$cameraLinks = Get-NetTCPConnection -RemotePort 81 -State Established -ErrorAction SilentlyContinue
if ($cameraLinks) {
    $owners = ($cameraLinks | Select-Object -ExpandProperty OwningProcess -Unique) -join ", "
    Write-Warning "A process outside this project still holds the camera stream (PID $owners). Close any CameraWebServer preview before the next run."
}

Write-Host "rPLA live inspection services are stopped." -ForegroundColor Yellow

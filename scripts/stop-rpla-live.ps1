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

Write-Host "rPLA live inspection services are stopped." -ForegroundColor Yellow

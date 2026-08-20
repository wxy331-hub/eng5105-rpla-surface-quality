param(
    [string]$CameraIp = "",
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

function Get-LocalIPv4Address {
    return @(
        Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
            Where-Object { $_.IPAddress -notlike "127.*" } |
            Select-Object -ExpandProperty IPAddress
    )
}

function Test-CameraEndpoint {
    param([string]$Ip, [int]$TimeoutSeconds = 3)
    try {
        $status = Invoke-RestMethod -Uri "http://$Ip/status" -TimeoutSec $TimeoutSeconds
        return ($null -ne $status.framesize)
    } catch {
        return $false
    }
}

function Find-CameraOnLocalSubnets {
    # The ESP32 takes a DHCP lease from the hotspot, so its address moves whenever
    # the network changes. Probe port 81 (the CameraWebServer stream) across each
    # local subnet, then confirm the survivors actually answer /status.
    $localAddresses = Get-LocalIPv4Address
    $adapters = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object {
            $_.IPAddress -notlike "127.*" -and
            $_.IPAddress -notlike "169.254.*" -and
            $_.PrefixLength -ge 24
        }

    $reachable = @()
    foreach ($adapter in $adapters) {
        $parts = $adapter.IPAddress.Split(".")
        $blockSize = [int][math]::Pow(2, 32 - $adapter.PrefixLength)
        $networkLast = [int]$parts[3] - ([int]$parts[3] % $blockSize)
        $subnetPrefix = "$($parts[0]).$($parts[1]).$($parts[2])"

        $pending = @()
        for ($octet = $networkLast + 1; $octet -le $networkLast + $blockSize - 2; $octet++) {
            $candidate = "$subnetPrefix.$octet"
            if ($localAddresses -contains $candidate) { continue }
            $client = New-Object System.Net.Sockets.TcpClient
            $pending += [pscustomobject]@{
                Ip     = $candidate
                Client = $client
                Handle = $client.BeginConnect($candidate, 81, $null, $null)
            }
        }
        Start-Sleep -Milliseconds 900
        foreach ($probe in $pending) {
            if ($probe.Handle.IsCompleted) {
                try {
                    $probe.Client.EndConnect($probe.Handle)
                    $reachable += $probe.Ip
                } catch { }
            }
            $probe.Client.Close()
        }
    }

    return @($reachable | Where-Object { Test-CameraEndpoint -Ip $_ })
}

function Resolve-CameraIp {
    param([string]$Requested, [string]$Configured)
    $localAddresses = Get-LocalIPv4Address

    if ($Requested) {
        if ($localAddresses -contains $Requested) {
            throw "-CameraIp $Requested is this computer's own address, not the camera. The hotspot reassigns leases when the network changes, so an address that used to belong to the ESP32 can end up on this machine. Run the script without -CameraIp to discover the camera."
        }
        return $Requested
    }

    if ($Configured -and ($localAddresses -notcontains $Configured) -and (Test-CameraEndpoint -Ip $Configured)) {
        return $Configured
    }

    Write-Host "Looking for the ESP32 camera on the local network..." -ForegroundColor Cyan
    # @() matters: a single-element array unrolls to a scalar on return, and
    # indexing a bare string would yield its first character instead of the address.
    $found = @(Find-CameraOnLocalSubnets)
    if ($found.Count -eq 1) {
        Write-Host "Found the camera at $($found[0])." -ForegroundColor Green
        return $found[0]
    }
    if ($found.Count -gt 1) {
        throw "More than one ESP32 camera answered: $($found -join ', '). Re-run with -CameraIp <address> to choose one."
    }
    throw "No ESP32 camera answered on any local subnet. Check that the board is powered, that its firmware carries the current Wi-Fi credentials (re-flash after changing the SSID or password), and that this computer is on the same network. Pass -CameraIp <address> to skip discovery."
}

function Find-NodeExecutable {
    $systemNode = Get-Command node.exe -ErrorAction SilentlyContinue
    if ($systemNode) { return $systemNode.Source }

    $codexNode = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"
    if (Test-Path -LiteralPath $codexNode) { return $codexNode }

    throw "Node.js is required to start the GUI. Install Node.js 20 or later, then run START_RPLA_LIVE.cmd again."
}

$CameraIp = Resolve-CameraIp -Requested $CameraIp -Configured ([string]$serviceConfig.camera_ip)

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
    -ArgumentList @("-m", "uvicorn", "src.live_service:app", "--app-dir", "`"$projectRoot`"", "--host", "127.0.0.1", "--port", "8765") `
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
    -ArgumentList @("`"$viteEntry`"", "--mode", "live", "--host", "127.0.0.1", "--port", "5173") `
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

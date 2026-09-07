param(
    [ValidateSet("esp32_mjpeg", "usb_uvc")]
    [string]$SourceType = "",
    [string]$CameraIp = "",
    [string]$CameraDevice = "",
    [ValidateSet("auto", "dshow", "msmf", "v4l2")]
    [string]$CameraBackend = "",
    [string]$Resolution = "",
    [Alias("ValidateOnly")]
    [switch]$CheckConfig,
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
if (-not (Test-Path -LiteralPath $serviceConfigPath)) {
    throw "Live service configuration is missing: $serviceConfigPath"
}

$serviceConfig = Get-Content -Raw -Encoding utf8 $serviceConfigPath | ConvertFrom-Json
if (-not $SourceType) {
    if ($serviceConfig.default_source_type) {
        $SourceType = [string]$serviceConfig.default_source_type
    } else {
        $SourceType = "esp32_mjpeg"
    }
}
$SourceType = $SourceType.ToLowerInvariant()
if ($SourceType -notin @("esp32_mjpeg", "usb_uvc")) {
    throw "Unsupported camera source in live_service.json: $SourceType"
}
if ($serviceConfig.sources) {
    $sourceConfig = $serviceConfig.sources.PSObject.Properties[$SourceType].Value
} elseif ($SourceType -eq "esp32_mjpeg") {
    # Keep the original flat ESP32 configuration usable.
    $sourceConfig = $serviceConfig
} else {
    $sourceConfig = $null
}
if (-not $sourceConfig) {
    throw "Camera source is missing from live_service.json: $SourceType"
}
if (-not $Resolution) { $Resolution = [string]$sourceConfig.default_resolution }
$Resolution = $Resolution.ToUpperInvariant()
$resolutionProfile = $sourceConfig.resolution_profiles.PSObject.Properties[$Resolution].Value
if (-not $resolutionProfile) {
    throw "Resolution profile '$Resolution' is missing for camera source '$SourceType' in live_service.json."
}
function ConvertTo-PositiveFrameDimension {
    param($Value, [string]$Name)
    $message = "Resolution profile '$Resolution' $Name must be a positive integer."
    if ($null -eq $Value -or $Value -is [bool]) { throw $message }
    if ($Value -is [string] -and $Value.Trim() -cnotmatch '^\+?[0-9]+$') { throw $message }
    try { $numericValue = [double]$Value }
    catch { throw $message }
    if ([double]::IsNaN($numericValue) -or [double]::IsInfinity($numericValue) -or
        $numericValue -le 0 -or [math]::Truncate($numericValue) -ne $numericValue) {
        throw $message
    }
    try { return [int]$numericValue }
    catch { throw $message }
}
$resolutionWidth = ConvertTo-PositiveFrameDimension -Value $resolutionProfile.width_px -Name "width_px"
$resolutionHeight = ConvertTo-PositiveFrameDimension -Value $resolutionProfile.height_px -Name "height_px"

if ($SourceType -eq "usb_uvc") {
    if (-not $CameraDevice) { $CameraDevice = [string]$sourceConfig.device }
    $CameraDevice = $CameraDevice.Trim()
    if (-not $CameraDevice) { throw "USB camera device is missing; set -CameraDevice or sources.usb_uvc.device." }
    if ($CameraDevice -cmatch '^[0-9]+$') {
        $resolvedDevice = [int]$CameraDevice
    } elseif ($CameraDevice -cmatch '^/dev/(?:video[0-9]+|v4l/(?:by-id|by-path)/[^/\\]+)$' -and
              (($CameraDevice -split '/')[-1] -notin @('.', '..'))) {
        if (Test-Path -LiteralPath $CameraDevice) {
            $deviceItem = Get-Item -LiteralPath $CameraDevice
            if (-not ($deviceItem.Attributes -band [System.IO.FileAttributes]::Device)) {
                throw "USB camera device path must name a character device, not an existing file or directory."
            }
        }
        $resolvedDevice = $CameraDevice
    } else {
        throw "USB camera device must be a non-negative index or local /dev/videoN, /dev/v4l/by-id or /dev/v4l/by-path device path."
    }
    if (-not $CameraBackend) {
        if ($sourceConfig.backend) {
            $CameraBackend = [string]$sourceConfig.backend
        } else {
            $CameraBackend = "auto"
        }
    }
    $CameraBackend = $CameraBackend.ToLowerInvariant()
    if ($CameraBackend -notin @("auto", "dshow", "msmf", "v4l2")) {
        throw "Unsupported USB camera backend: $CameraBackend"
    }
    if ($resolvedDevice -is [string] -and $CameraBackend -in @("dshow", "msmf")) {
        throw "Windows USB camera backends dshow and msmf require a numeric device index."
    }
    $requestedPixelFormat = "MJPG"
    if ($resolutionProfile.PSObject.Properties['pixel_format']) {
        $requestedPixelFormat = ([string]$resolutionProfile.pixel_format).ToUpperInvariant()
    }
    if ($requestedPixelFormat -notin @("MJPG", "YUY2", "YUYV")) {
        throw "Unsupported USB pixel_format '$requestedPixelFormat'; choose MJPG, YUY2 or YUYV."
    }
    $requestedFps = $null
    if ($null -ne $resolutionProfile.fps) {
        if ($resolutionProfile.fps -is [bool]) { throw "USB fps must be a positive finite number or null." }
        try { $requestedFps = [double]$resolutionProfile.fps }
        catch { throw "USB fps must be a positive finite number or null." }
        if ([double]::IsNaN($requestedFps) -or [double]::IsInfinity($requestedFps) -or $requestedFps -le 0) {
            throw "USB fps must be a positive finite number or null."
        }
    }
    $connectionPlan = [ordered]@{
        device = $resolvedDevice
        backend = $CameraBackend
        connection_status = "PENDING_HARDWARE_CONNECTION"
        network_discovery = $false
        esp32_http_control = $false
    }
} else {
    if ($null -eq $resolutionProfile.framesize_control_value) {
        throw "ESP32 resolution profile '$Resolution' is missing framesize_control_value."
    }
    $frameSizeValue = [int]$resolutionProfile.framesize_control_value
    $configuredCameraIp = [string]$sourceConfig.camera_ip
    $requestedOrConfiguredIp = $configuredCameraIp
    if ($CameraIp) { $requestedOrConfiguredIp = $CameraIp }
    $connectionPlan = [ordered]@{
        requested_or_configured_ip = $requestedOrConfiguredIp
        framesize_control_value = $frameSizeValue
        connection_status = "PENDING_HARDWARE_CONNECTION"
        network_discovery = -not [bool]$CameraIp
        esp32_http_control = $true
    }
}

if ($CheckConfig) {
    # This path deliberately stops before filesystem, environment, network or
    # process changes, and does not open a camera to check advertised modes.
    [ordered]@{
        status = "CONFIGURATION_ONLY"
        source_type = $SourceType
        source_name = [string]$sourceConfig.source_name
        inspection_profile = [string]$sourceConfig.inspection_profile
        resolution = $Resolution
        requested_width_px = $resolutionWidth
        requested_height_px = $resolutionHeight
        requested_pixel_format = $requestedPixelFormat
        requested_fps = $requestedFps
        connection = $connectionPlan
        hardware_verified = $false
    } | ConvertTo-Json -Depth 5
    return
}

if (-not (Test-Path -LiteralPath $python)) {
    throw "Python virtual environment is missing: $python"
}
if (-not (Test-Path -LiteralPath $guiRoot)) {
    throw "GUI project is missing: $guiRoot"
}

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
    if ($SourceType -eq "usb_uvc") {
        throw "The Python service started, but no USB camera frame arrived within $TimeoutSeconds seconds. Check device '$CameraDevice', backend '$CameraBackend', USB connection and requested profile '$Resolution'; close other applications using this camera. See $backendErrorLog."
    }
    throw "The Python service started, but no ESP32 frame arrived within $TimeoutSeconds seconds. Close any ESP32 CameraWebServer preview and check camera $CameraIp. See $backendErrorLog."
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

if ($SourceType -eq "esp32_mjpeg") {
    $CameraIp = Resolve-CameraIp -Requested $CameraIp -Configured $configuredCameraIp
}

Stop-ProjectListener -Port 8765
Stop-ProjectListener -Port 5173
Start-Sleep -Seconds 1

$env:RPLA_SOURCE_TYPE = $SourceType
$env:RPLA_RESOLUTION = $Resolution
# Bind the backend to the same file this launcher resolved and checked.
$env:RPLA_CONFIG_PATH = $serviceConfigPath
if ($SourceType -eq "esp32_mjpeg") {
    $env:RPLA_CAMERA_DEVICE = $null
    $env:RPLA_CAMERA_BACKEND = $null
    $otherCameraClients = Get-NetTCPConnection -RemoteAddress $CameraIp -RemotePort 81 -State Established -ErrorAction SilentlyContinue
    if ($otherCameraClients) {
        throw "The ESP32 stream is already in use. Stop the CameraWebServer preview or another direct camera client, then run this script again."
    }

    $controlUrl = "http://$CameraIp/control?var=framesize&val=$frameSizeValue"
    $statusUrl = "http://$CameraIp/status"
    Invoke-WebRequest -UseBasicParsing -Uri $controlUrl -TimeoutSec 8 | Out-Null
    $cameraStatus = Invoke-RestMethod -Uri $statusUrl -TimeoutSec 8
    if ([int]$cameraStatus.framesize -ne $frameSizeValue) {
        throw "The ESP32 camera did not accept $Resolution framesize $frameSizeValue."
    }
    $env:RPLA_CAMERA_IP = $CameraIp
    $env:RPLA_STREAM_URL = "http://${CameraIp}:81/stream"
    $env:RPLA_CONTROL_URL = "http://$CameraIp"
    $env:RPLA_FRAMESIZE = [string]$frameSizeValue
} else {
    # The backend is the sole USB camera owner. Discovery and camera opening
    # belong to its acquisition adapter, so no pre-launch device open occurs.
    $env:RPLA_CAMERA_IP = $null
    $env:RPLA_STREAM_URL = $null
    $env:RPLA_CONTROL_URL = $null
    $env:RPLA_FRAMESIZE = $null
    $env:RPLA_CAMERA_DEVICE = $CameraDevice
    $env:RPLA_CAMERA_BACKEND = $CameraBackend
}

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
if ($SourceType -eq "usb_uvc") {
    Write-Host "Camera: USB device '$CameraDevice', backend '$CameraBackend'; requested $Resolution ${resolutionWidth}x${resolutionHeight}."
    Write-Host "Check the GUI camera status for the negotiated mode and hardware connection state."
} else {
    Write-Host "Camera: ESP32 $Resolution ${resolutionWidth}x${resolutionHeight} at $CameraIp"
}
Write-Host "API:    http://127.0.0.1:8765/api/health"
Write-Host "GUI:    http://127.0.0.1:5173/"
Write-Host "Logs:   $runtimeRoot"

if (-not $NoBrowser) {
    Start-Process "http://127.0.0.1:5173/"
}

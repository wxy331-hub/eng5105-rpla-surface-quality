param(
    [string]$CameraIp = "172.20.10.2",
    [string]$ApiBaseUrl = "http://127.0.0.1:8765",
    [int]$FaultHoldSeconds = 4,
    [int]$TimeoutSeconds = 25,
    [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$ruleName = "rPLA OV3660 real network fault test"
if (-not $OutputPath) {
    $runId = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ") + "_" + [guid]::NewGuid().ToString("N").Substring(0, 10)
    $OutputPath = Join-Path $projectRoot "data\output\network_fault\network_fault_$runId.json"
}
$OutputPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($OutputPath)
if (Test-Path -LiteralPath $OutputPath) {
    throw "Output already exists: $OutputPath"
}
$outputDirectory = Split-Path -Parent $OutputPath
New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null

function Get-Health {
    Invoke-RestMethod -Uri "$ApiBaseUrl/api/health" -TimeoutSec 3
}

function Wait-HealthCondition {
    param(
        [scriptblock]$Condition,
        [int]$Timeout,
        [string]$FailureMessage
    )
    $deadline = (Get-Date).AddSeconds($Timeout)
    do {
        try {
            $health = Get-Health
            if (& $Condition $health) { return $health }
        } catch {
            # The resident API should remain available while only the camera path is blocked.
        }
        Start-Sleep -Milliseconds 100
    } while ((Get-Date) -lt $deadline)
    throw $FailureMessage
}

$initial = Get-Health
if ($initial.camera_state -ne "HEALTHY") {
    throw "The camera must be HEALTHY before fault injection; current state: $($initial.camera_state)"
}
if ([int]$initial.frame_width_px -ne 800 -or [int]$initial.frame_height_px -ne 600) {
    throw "The real network fault test must use the selected SVGA 800x600 profile."
}

$streamConnection = Get-NetTCPConnection -RemoteAddress $CameraIp -RemotePort 81 -State Established -ErrorAction SilentlyContinue |
    Where-Object { $_.OwningProcess -ne 0 } |
    Select-Object -First 1
if (-not $streamConnection) {
    throw "No established resident-service connection to ${CameraIp}:81 was found."
}
$streamProcess = Get-Process -Id $streamConnection.OwningProcess -ErrorAction Stop
$streamProcessDetails = Get-CimInstance Win32_Process -Filter "ProcessId = $($streamConnection.OwningProcess)" -ErrorAction Stop
if (-not $streamProcessDetails.CommandLine.Contains($projectRoot) -or -not $streamProcessDetails.CommandLine.Contains("src.live_service:app")) {
    throw "The active camera client is not the project resident service: $($streamProcessDetails.CommandLine)"
}
$firewallProgram = $streamProcess.Path

$faultStarted = $null
$faultObserved = $null
$faultHealth = $null
$blockedHealth = $null
$recoveryStarted = $null
$recovered = $null
$recoveredHealth = $null
$ruleCreated = $false

try {
    Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule
    $faultStarted = Get-Date
    $createdRule = New-NetFirewallRule `
        -DisplayName $ruleName `
        -Direction Outbound `
        -Action Block `
        -Program $firewallProgram `
        -RemoteAddress $CameraIp `
        -Profile Any `
        -ErrorAction Stop
    if (-not $createdRule -or -not (Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue)) {
        throw "Windows did not create the scoped firewall rule; run this test from an elevated PowerShell session."
    }
    $ruleCreated = $true

    Invoke-RestMethod -Method Post -Uri "$ApiBaseUrl/api/control/reconnect" -TimeoutSec 3 | Out-Null
    $faultHealth = Wait-HealthCondition `
        -Condition { param($value) $value.camera_state -ne "HEALTHY" -and -not $value.automatic_actions_allowed } `
        -Timeout $TimeoutSeconds `
        -FailureMessage "The service did not enter a fail-safe state after the camera route was blocked."
    $faultObserved = Get-Date

    Start-Sleep -Seconds $FaultHoldSeconds
    $blockedHealth = Get-Health
    $faultHoldFrameAdvance = [int]$blockedHealth.frames_received - [int]$faultHealth.frames_received
    if ($blockedHealth.camera_state -eq "HEALTHY" -or $blockedHealth.automatic_actions_allowed -or $blockedHealth.detection_active) {
        throw "The service left the fail-safe state while the real camera route was still blocked."
    }
    if ($faultHoldFrameAdvance -gt 1) {
        throw "Frames continued to advance after the service reported the camera fault: $faultHoldFrameAdvance"
    }
} finally {
    if ($ruleCreated) {
        Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule
    }
}

$recoveryStarted = Get-Date
Invoke-RestMethod -Method Post -Uri "$ApiBaseUrl/api/control/reconnect" -TimeoutSec 3 | Out-Null
$minimumRecoveredFrame = [int]$blockedHealth.frames_received + 1
$recoveredHealth = Wait-HealthCondition `
    -Condition { param($value) $value.camera_state -eq "HEALTHY" -and [int]$value.frames_received -ge $minimumRecoveredFrame } `
    -Timeout $TimeoutSeconds `
    -FailureMessage "The camera did not recover after the firewall rule was removed."
$recovered = Get-Date

$result = [ordered]@{
    evidence_level = "LIVE_REAL_NETWORK_FAULT_AND_RECOVERY"
    tested_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    camera_path = "PLAN_B_ESP32S3_OV3660_MJPEG"
    resolution = "SVGA 800x600"
    fault_method = "Temporary outbound firewall block scoped to the verified resident-service executable and camera IP"
    blocked_program = $firewallProgram
    initial_state = $initial.camera_state
    fault_state = $faultHealth.camera_state
    blocked_state_after_hold = $blockedHealth.camera_state
    automatic_actions_allowed_during_fault = [bool]$blockedHealth.automatic_actions_allowed
    detection_active_during_fault = [bool]$blockedHealth.detection_active
    frames_before_fault = [int]$initial.frames_received
    frames_when_fault_observed = [int]$faultHealth.frames_received
    frames_during_fault = [int]$blockedHealth.frames_received
    frames_advanced_while_fault_held = $faultHoldFrameAdvance
    fault_detection_latency_ms = [math]::Round(($faultObserved - $faultStarted).TotalMilliseconds, 2)
    fault_hold_seconds = $FaultHoldSeconds
    recovered_state = $recoveredHealth.camera_state
    frames_after_recovery = [int]$recoveredHealth.frames_received
    recovery_latency_ms = [math]::Round(($recovered - $recoveryStarted).TotalMilliseconds, 2)
    firewall_rule_removed = -not [bool](Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue)
}

# CreateNew also refuses a file created by another run during fault injection.
$outputStream = [System.IO.File]::Open($OutputPath, [System.IO.FileMode]::CreateNew)
try {
    $bytes = [System.Text.Encoding]::UTF8.GetBytes(($result | ConvertTo-Json -Depth 5) + [Environment]::NewLine)
    $outputStream.Write($bytes, 0, $bytes.Length)
} finally {
    $outputStream.Dispose()
}
$result | ConvertTo-Json -Depth 5
Write-Host "Saved: $OutputPath"

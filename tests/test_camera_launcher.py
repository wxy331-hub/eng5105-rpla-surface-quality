"""Run the Windows launcher with hardware/process boundaries replaced in PowerShell."""

import json
from pathlib import Path
import shutil
import subprocess

import pytest


POWERSHELL = shutil.which("powershell.exe")
pytestmark = pytest.mark.skipif(POWERSHELL is None, reason="Windows launcher requires PowerShell")
LAUNCHER = Path(__file__).resolve().parents[1] / "scripts" / "start-rpla-live.ps1"


@pytest.fixture
def launcher_project(tmp_path: Path) -> Path:
    root = tmp_path / "launcher project"
    (root / "scripts").mkdir(parents=True)
    (root / "config").mkdir()
    shutil.copyfile(LAUNCHER, root / "scripts" / LAUNCHER.name)
    config = {
        "default_source_type": "esp32_mjpeg",
        "sources": {
            "esp32_mjpeg": {
                "source_name": "ESP32S3_OV3660",
                "camera_ip": "192.0.2.10",
                "default_resolution": "SVGA",
                "inspection_profile": "plan_b",
                "resolution_profiles": {
                    "SVGA": {"framesize_control_value": 11, "width_px": 800, "height_px": 600},
                    "VGA": {"framesize_control_value": 10, "width_px": 640, "height_px": 480},
                },
            },
            "usb_uvc": {
                "source_name": "ALC_IMX258_USB",
                "device": 0,
                "backend": "auto",
                "default_resolution": "UHD",
                "inspection_profile": "plan_a",
                "resolution_profiles": {
                    "UHD": {"width_px": 3840, "height_px": 2160, "pixel_format": "MJPG", "fps": 30},
                },
            },
        },
    }
    (root / "config" / "live_service.json").write_text(json.dumps(config), encoding="utf-8")
    return root


def run_powershell(root: Path, body: str) -> subprocess.CompletedProcess[str]:
    wrapper = root / "test_wrapper.ps1"
    script_path = str(root / "scripts" / LAUNCHER.name).replace("'", "''")
    wrapper.write_text(
        "$ErrorActionPreference = 'Stop'\n"
        f"$launcher = '{script_path}'\n" + body,
        encoding="utf-8-sig",
    )
    return subprocess.run(
        [POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(wrapper)],
        capture_output=True,
        text=True,
        timeout=20,
    )


@pytest.mark.parametrize(
    ("arguments", "source", "resolution", "device", "backend"),
    [
        ("", "esp32_mjpeg", "SVGA", None, None),
        ("-SourceType esp32_mjpeg -Resolution VGA", "esp32_mjpeg", "VGA", None, None),
        ("-SourceType usb_uvc", "usb_uvc", "UHD", 0, "auto"),
        ("-SourceType usb_uvc -CameraDevice 2 -CameraBackend dshow", "usb_uvc", "UHD", 2, "dshow"),
        ("-SourceType usb_uvc -CameraDevice /dev/video2 -CameraBackend v4l2", "usb_uvc", "UHD", "/dev/video2", "v4l2"),
        ("-SourceType usb_uvc -CameraDevice /dev/v4l/by-id/camera-0 -CameraBackend v4l2", "usb_uvc", "UHD", "/dev/v4l/by-id/camera-0", "v4l2"),
    ],
)
def test_check_config_selects_source_without_side_effects(
    launcher_project: Path, arguments: str, source: str, resolution: str, device, backend
) -> None:
    result = run_powershell(
        launcher_project,
        """
function Get-NetIPAddress { throw 'Network discovery is forbidden' }
function Get-NetTCPConnection { throw 'Network inspection is forbidden' }
function Invoke-WebRequest { throw 'HTTP is forbidden' }
function Invoke-RestMethod { throw 'HTTP is forbidden' }
function Start-Process { throw 'Process launch is forbidden' }
$env:RPLA_SOURCE_TYPE = 'unchanged-source'
$env:RPLA_RESOLUTION = 'unchanged-resolution'
$env:RPLA_CAMERA_IP = 'unchanged-ip'
$env:RPLA_CONFIG_PATH = 'unchanged-config'
"""
        + f"$resolved = (& $launcher -CheckConfig {arguments}) | ConvertFrom-Json\n"
        + """
if ($env:RPLA_SOURCE_TYPE -ne 'unchanged-source' -or
    $env:RPLA_RESOLUTION -ne 'unchanged-resolution' -or
    $env:RPLA_CAMERA_IP -ne 'unchanged-ip' -or
    $env:RPLA_CONFIG_PATH -ne 'unchanged-config') { throw 'CheckConfig changed environment' }
$resolved | ConvertTo-Json -Depth 5
""",
    )
    assert result.returncode == 0, result.stderr
    resolved = json.loads(result.stdout)
    assert resolved["source_type"] == source
    assert resolved["resolution"] == resolution
    assert resolved["hardware_verified"] is False
    assert resolved["connection"]["connection_status"] == "PENDING_HARDWARE_CONNECTION"
    assert not (launcher_project / "data").exists()
    if source == "usb_uvc":
        assert resolved["connection"]["device"] == device
        assert resolved["connection"]["backend"] == backend
        assert resolved["connection"]["network_discovery"] is False
        assert resolved["connection"]["esp32_http_control"] is False


def test_validate_only_alias_accepts_legacy_flat_config(launcher_project: Path) -> None:
    config_path = launcher_project / "config" / "live_service.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config_path.write_text(json.dumps(config["sources"]["esp32_mjpeg"]), encoding="utf-8")
    result = run_powershell(launcher_project, "& $launcher -ValidateOnly\n")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["resolution"] == "SVGA"


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ("-SourceType usb_uvc -Resolution SVGA", "missing for camera source 'usb_uvc'"),
        ("-SourceType usb_uvc -CameraDevice http://192.0.2.10/stream", "non-negative index or local /dev/videoN"),
        ("-SourceType usb_uvc -CameraDevice sample.mp4", "non-negative index or local /dev/videoN"),
        ("-SourceType usb_uvc -CameraDevice /dev/v4l/by-id/..", "non-negative index or local /dev/videoN"),
        ("-SourceType usb_uvc -CameraDevice /dev/video2 -CameraBackend dshow", "require a numeric device index"),
        ("-SourceType usb_uvc -CameraDevice /dev/video2 -CameraBackend msmf", "require a numeric device index"),
    ],
)
def test_check_config_rejects_incompatible_usb_selection(
    launcher_project: Path, arguments: str, message: str
) -> None:
    result = run_powershell(launcher_project, f"& $launcher -CheckConfig {arguments}\n")
    assert result.returncode != 0
    assert message in result.stderr
    assert not (launcher_project / "data").exists()


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("pixel_format", "H264", "Unsupported USB pixel_format"),
        ("pixel_format", None, "Unsupported USB pixel_format"),
        ("fps", 0, "positive finite number"),
        ("fps", -1, "positive finite number"),
        ("fps", "NaN", "positive finite number"),
        ("fps", "Infinity", "positive finite number"),
        ("fps", "not-a-rate", "positive finite number"),
        ("width_px", 3840.4, "width_px must be a positive integer"),
        ("height_px", 2160.4, "height_px must be a positive integer"),
        ("width_px", True, "width_px must be a positive integer"),
        ("height_px", False, "height_px must be a positive integer"),
        ("width_px", "NaN", "width_px must be a positive integer"),
        ("height_px", "Infinity", "height_px must be a positive integer"),
        ("width_px", None, "width_px must be a positive integer"),
        ("height_px", 0, "height_px must be a positive integer"),
    ],
)
def test_check_config_rejects_invalid_usb_capture_profile(
    launcher_project: Path, field: str, value, message: str
) -> None:
    config_path = launcher_project / "config" / "live_service.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["sources"]["usb_uvc"]["resolution_profiles"]["UHD"][field] = value
    config_path.write_text(json.dumps(config), encoding="utf-8")
    result = run_powershell(launcher_project, "& $launcher -SourceType usb_uvc -CheckConfig\n")
    assert result.returncode != 0
    assert message in result.stderr
    assert not (launcher_project / "data").exists()


@pytest.mark.parametrize("source", ["usb_uvc", "esp32_mjpeg"])
def test_real_launch_branch_prepares_only_selected_source(
    launcher_project: Path, source: str
) -> None:
    # Presence checks pass, but the fake Start-Process never executes this file.
    python = launcher_project / ".venv" / "Scripts" / "python.exe"
    python.parent.mkdir(parents=True)
    python.touch()
    (launcher_project / "gui-prototype").mkdir()
    result = run_powershell(
        launcher_project,
        """
$global:httpRequests = @()
function Start-Sleep { }
function Get-NetTCPConnection {
    param($LocalPort, $RemoteAddress, $RemotePort, $State)
    if ($env:RPLA_SOURCE_TYPE -eq 'usb_uvc' -and $RemotePort) { throw 'USB probed an ESP32 port' }
    return @()
}
function Get-NetIPAddress {
    if ($env:TEST_SELECTED_SOURCE -eq 'usb_uvc') { throw 'USB attempted IP discovery' }
    return [pscustomobject]@{ IPAddress = '192.0.2.20' }
}
function Invoke-WebRequest {
    param($Uri, $TimeoutSec, [switch]$UseBasicParsing)
    if ($env:TEST_SELECTED_SOURCE -eq 'usb_uvc') { throw 'USB attempted ESP32 HTTP control' }
    $global:httpRequests += $Uri
    return [pscustomobject]@{ StatusCode = 200 }
}
function Invoke-RestMethod {
    param($Uri, $TimeoutSec)
    if ($env:TEST_SELECTED_SOURCE -eq 'usb_uvc') { throw 'USB attempted ESP32 HTTP status' }
    $global:httpRequests += $Uri
    return [pscustomobject]@{ framesize = 11 }
}
function Start-Process {
    param($FilePath, $ArgumentList, $WorkingDirectory, $WindowStyle, $RedirectStandardOutput, $RedirectStandardError)
    if ($ArgumentList[1] -ne 'uvicorn') { throw 'Unexpected process launch' }
    $global:launchEnvironment = [ordered]@{
        source_type = $env:RPLA_SOURCE_TYPE
        resolution = $env:RPLA_RESOLUTION
        device = $env:RPLA_CAMERA_DEVICE
        backend = $env:RPLA_CAMERA_BACKEND
        camera_ip = $env:RPLA_CAMERA_IP
        stream_url = $env:RPLA_STREAM_URL
        control_url = $env:RPLA_CONTROL_URL
        framesize = $env:RPLA_FRAMESIZE
        config_path = $env:RPLA_CONFIG_PATH
        http_requests = @($global:httpRequests)
        window_style = $WindowStyle
    }
    throw 'CAPTURED_BACKEND_LAUNCH'
}
$env:RPLA_CAMERA_IP = 'stale-ip'
$env:RPLA_STREAM_URL = 'stale-stream'
$env:RPLA_CONTROL_URL = 'stale-control'
$env:RPLA_FRAMESIZE = '19'
$env:RPLA_CAMERA_DEVICE = '99'
$env:RPLA_CAMERA_BACKEND = 'msmf'
$env:RPLA_SOURCE_TYPE = 'previous-source'
$env:RPLA_RESOLUTION = 'previous-resolution'
$env:RPLA_CONFIG_PATH = 'previous-config.json'
"""
        + f"$env:TEST_SELECTED_SOURCE = '{source}'\n"
        + f"try {{ & $launcher -SourceType {source} -CameraIp 192.0.2.10 -NoBrowser }}\n"
        + """
catch { if ($_.Exception.Message -ne 'CAPTURED_BACKEND_LAUNCH') { throw } }
if (-not $global:launchEnvironment) { throw 'Backend launch boundary was not reached' }
$global:launchEnvironment | ConvertTo-Json -Depth 5
""",
    )
    assert result.returncode == 0, result.stderr
    prepared = json.loads(result.stdout)
    assert prepared["source_type"] == source
    assert prepared["window_style"] == "Hidden"
    assert Path(prepared["config_path"]) == launcher_project / "config" / "live_service.json"
    if source == "usb_uvc":
        assert prepared["resolution"] == "UHD"
        assert prepared["device"] == "0"
        assert prepared["backend"] == "auto"
        assert prepared["http_requests"] == []
        assert all(prepared[key] is None for key in ("camera_ip", "stream_url", "control_url", "framesize"))
    else:
        assert prepared["resolution"] == "SVGA"
        assert prepared["framesize"] == "11"
        assert prepared["device"] is None
        assert prepared["backend"] is None
        assert prepared["stream_url"] == "http://192.0.2.10:81/stream"
        assert prepared["control_url"] == "http://192.0.2.10"
        assert prepared["http_requests"] == [
            "http://192.0.2.10/control?var=framesize&val=11",
            "http://192.0.2.10/status",
        ]

"""Check the camera launcher without opening a device or starting a service."""

import json
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
POWERSHELL = shutil.which('powershell.exe')
pytestmark = pytest.mark.skipif(POWERSHELL is None, reason='Windows launcher requires PowerShell')


def run_script(tmp_path, body):
    path = tmp_path / 'wrapper.ps1'
    path.write_text("$ErrorActionPreference = 'Stop'\n" + body, encoding='utf-8-sig')
    return subprocess.run([POWERSHELL, '-NoProfile', '-NonInteractive', '-ExecutionPolicy',
                           'Bypass', '-File', str(path)], text=True, capture_output=True, timeout=30)


def test_camera_check_config_has_no_services_or_environment_side_effects(tmp_path):
    launcher = str(ROOT / 'scripts/start-rpla-week8.ps1').replace("'", "''")
    result = run_script(tmp_path, f"""
function Start-Process {{ throw 'Must not launch' }}
function Get-NetTCPConnection {{ throw 'Must not probe ports' }}
$env:RPLA_SOURCE_TYPE = 'old-source'
$env:VITE_INSPECTION_MODE = 'offline'
& '{launcher}' -CheckConfig -CameraDevice 2 -CameraBackend dshow -Resolution FHD
if ($env:RPLA_SOURCE_TYPE -ne 'old-source' -or $env:VITE_INSPECTION_MODE -ne 'offline') {{ throw 'Environment changed' }}
""")
    assert result.returncode == 0, result.stderr
    plan = json.loads(result.stdout)
    assert plan['source_type'] == 'usb_uvc'
    assert plan['connection']['device'] == 2
    assert plan['requested_width_px'] == 1920
    assert plan['hardware_verified'] is False
    assert plan['sample_service'] == 'http://127.0.0.1:8765/api/week7'


def test_camera_check_config_rejects_file_as_device(tmp_path):
    launcher = str(ROOT / 'scripts/start-rpla-week8.ps1').replace("'", "''")
    result = run_script(tmp_path, f"& '{launcher}' -CheckConfig -CameraDevice movie.mp4\n")
    assert result.returncode != 0
    assert 'non-negative index' in result.stderr


@pytest.mark.parametrize('override, expected_device, expected_width', [
    ('', 1, 3840),
    ('-CameraDevice 2 -Resolution FHD', 2, 1920),
])
def test_demo_configuration_uses_external_camera_and_separate_archive(
    tmp_path, override, expected_device, expected_width
):
    launcher = str(ROOT / 'scripts/start-rpla-week8.ps1').replace("'", "''")
    result = run_script(tmp_path, f"""
function Start-Process {{ throw 'Must not launch or open a browser' }}
function Get-NetTCPConnection {{ throw 'Must not probe ports' }}
& '{launcher}' -Demo -CheckConfig {override}
""")
    assert result.returncode == 0, result.stderr
    plan = json.loads(result.stdout)
    assert plan['demo_mode'] is True
    assert plan['connection']['device'] == expected_device
    assert plan['connection']['backend'] == 'dshow'
    assert plan['requested_width_px'] == expected_width
    assert Path(plan['sample_archive']) == ROOT / 'data/output/camera_demo'
    assert plan['hardware_verified'] is False


@pytest.mark.parametrize('options, archive', [
    ('', 'week8_service'),
    ('-Demo -NoBrowser -WaitForCamera', 'camera_demo'),
])
def test_camera_launcher_opens_gui_while_camera_disconnected_and_restores_environment(tmp_path, options, archive):
    root = tmp_path / 'project with spaces'
    for folder in ('scripts', 'config', '.venv/Scripts', 'gui-prototype/node_modules/vite/bin'):
        (root / folder).mkdir(parents=True, exist_ok=True)
    for filename in ('start-rpla-week8.ps1', 'start-rpla-live.ps1'):
        shutil.copyfile(ROOT / 'scripts' / filename, root / 'scripts' / filename)
    shutil.copyfile(ROOT / 'config/live_service.json', root / 'config/live_service.json')
    (root / '.venv/Scripts/python.exe').touch()
    (root / 'gui-prototype/node_modules/vite/bin/vite.js').touch()
    launcher = str(root / 'scripts/start-rpla-week8.ps1').replace("'", "''")
    result = run_script(tmp_path, f"""
$global:launches = @()
function Get-NetTCPConnection {{ return @() }}
function Start-Process {{
    param($FilePath, $WorkingDirectory, $WindowStyle, [switch]$PassThru, $ArgumentList,
          $RedirectStandardOutput, $RedirectStandardError)
    if ($WindowStyle -ne 'Hidden') {{ throw 'Visible helper process' }}
    $global:launches += [ordered]@{{arguments=$ArgumentList; source=$env:RPLA_SOURCE_TYPE;
        device=$env:RPLA_CAMERA_DEVICE; mode=$env:VITE_INSPECTION_MODE;
        sample=$env:VITE_SAMPLE_API_URL; api=$env:VITE_INSPECTION_API_URL;
        legacy=$env:RPLA_STREAM_URL}}
    return [pscustomobject]@{{Id=(10000 + $global:launches.Count); HasExited=$false; StartTime=(Get-Date)}}
}}
function Invoke-RestMethod {{ return [pscustomobject]@{{mode='plan_a_camera';camera=@{{status='DISCONNECTED';connected=$false}}}} }}
function Invoke-WebRequest {{ return [pscustomobject]@{{StatusCode=200}} }}
function Stop-Process {{ throw 'Successful launch must not stop a process' }}
$env:RPLA_SOURCE_TYPE = 'old-source'
$env:VITE_INSPECTION_MODE = 'offline'
$env:RPLA_STREAM_URL = 'stale-stream'
$env:VITE_SAMPLE_API_URL = 'old-api'
& '{launcher}' {options} | Out-Null
if ($env:RPLA_SOURCE_TYPE -ne 'old-source' -or $env:VITE_INSPECTION_MODE -ne 'offline' -or
    $env:RPLA_STREAM_URL -ne 'stale-stream' -or $env:VITE_SAMPLE_API_URL -ne 'old-api') {{ throw 'Environment not restored' }}
ConvertTo-Json -InputObject $global:launches -Depth 4
""")
    assert result.returncode == 0, result.stderr
    launched = json.loads(result.stdout)
    assert len(launched) == 2
    assert 'src.week8_service' in launched[0]['arguments']
    assert str(root / 'data/output' / archive) in launched[0]['arguments']
    if options:
        assert '--wait-for-camera' in launched[0]['arguments']
        assert launched[0]['device'] == '1'
    assert all(item['source'] == 'usb_uvc' and item['legacy'] is None for item in launched)
    assert launched[1]['mode'] == 'service'
    assert launched[1]['sample'] == launched[1]['api'] == 'http://127.0.0.1:8765'
    assert (root / 'data/output/week8_runtime/processes.json').exists()

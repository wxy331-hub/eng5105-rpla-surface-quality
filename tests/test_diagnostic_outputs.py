"""Diagnostic reruns must never replace historical evidence (no hardware used)."""

import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from src import measure_live_latency as latency


def test_latency_defaults_create_distinct_results(tmp_path, monkeypatch):
    monkeypatch.setattr(latency, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["measure_live_latency"])
    monkeypatch.setattr(latency, "measure", lambda args: {"evidence_level": "OFFLINE_TEST_ONLY"})
    for _ in range(2):
        assert latency.main() == 0
    outputs = list((tmp_path / "data/output/latency").glob("*.json"))
    assert len(outputs) == 2
    assert all(json.loads(path.read_text())["evidence_level"] == "OFFLINE_TEST_ONLY" for path in outputs)


def test_latency_refuses_existing_output_before_measurement(tmp_path, monkeypatch):
    output = tmp_path / "latency_20260811.json"
    output.write_bytes(b"historical evidence")
    monkeypatch.setattr(sys, "argv", ["measure_live_latency", "--output", str(output)])

    def forbidden(args):
        pytest.fail("Existing output must be rejected before camera controls are accessed")

    monkeypatch.setattr(latency, "measure", forbidden)
    with pytest.raises(FileExistsError):
        latency.main()
    assert output.read_bytes() == b"historical evidence"


def test_latency_does_not_replace_output_created_during_measurement(tmp_path, monkeypatch):
    output = tmp_path / "result.json"
    monkeypatch.setattr(sys, "argv", ["measure_live_latency", "--output", str(output)])

    def measure(args):
        output.write_bytes(b"other run")
        return {"evidence_level": "OFFLINE_TEST_ONLY"}

    monkeypatch.setattr(latency, "measure", measure)
    with pytest.raises(FileExistsError):
        latency.main()
    assert output.read_bytes() == b"other run"


POWERSHELL = shutil.which("powershell.exe")
FAULT_SCRIPT = Path(__file__).resolve().parents[1] / "scripts/test-real-network-fault.ps1"


@pytest.mark.skipif(POWERSHELL is None, reason="Windows diagnostic requires PowerShell")
@pytest.mark.parametrize("existing", [False, True])
def test_network_fault_output_protection_with_mocked_hardware(tmp_path, existing):
    (tmp_path / "scripts").mkdir()
    script = tmp_path / "scripts" / FAULT_SCRIPT.name
    shutil.copyfile(FAULT_SCRIPT, script)
    output = tmp_path / "data/output/network_fault/network_fault_20260811.json"
    output.parent.mkdir(parents=True)
    output.write_bytes(b"historical evidence")
    # Every host/network boundary is replaced before the real diagnostic is run.
    wrapper = tmp_path / "run.ps1"
    wrapper.write_text(
        """
$ErrorActionPreference = 'Stop'
$global:healthCalls = 0
$global:rulePresent = $false
function Invoke-RestMethod {
    param($Method, $Uri, $TimeoutSec)
    if ($Method -eq 'Post') { return }
    $global:healthCalls++
    if ($global:rejectHardware) { throw 'Unexpected hardware access' }
    $fault = $global:healthCalls -in @(2, 3)
    return [pscustomobject]@{
        camera_state = $(if ($fault) { 'DISCONNECTED' } else { 'HEALTHY' })
        frame_width_px = 800; frame_height_px = 600
        automatic_actions_allowed = -not $fault; detection_active = -not $fault
        frames_received = $(if ($global:healthCalls -eq 4) { 12 } else { 10 })
    }
}
function Get-NetTCPConnection { [pscustomobject]@{ OwningProcess = 123 } }
function Get-Process { [pscustomobject]@{ Path = 'mock-python.exe' } }
function Get-CimInstance { [pscustomobject]@{ CommandLine = "$PSScriptRoot src.live_service:app" } }
function Get-NetFirewallRule { if ($global:rulePresent) { 'mock-rule' } }
function New-NetFirewallRule { $global:rulePresent = $true; 'mock-rule' }
function Remove-NetFirewallRule { $global:rulePresent = $false }
function Start-Sleep {}
$diagnostic = Join-Path $PSScriptRoot 'scripts/test-real-network-fault.ps1'
"""
        + (
            """
$global:rejectHardware = $true
try {
    & $diagnostic -OutputPath (Join-Path $PSScriptRoot 'data/output/network_fault/network_fault_20260811.json')
    throw 'Expected output rejection'
} catch {
    if ($_.Exception.Message -notlike '*already exists*') { throw }
}
if ($global:healthCalls -ne 0) { throw 'Output was checked after hardware access' }
"""
            if existing else
            """
& $diagnostic | Out-Null
$global:healthCalls = 0
& $diagnostic | Out-Null
"""
        ), encoding="utf-8-sig",
    )
    result = subprocess.run(
        [POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(wrapper)],
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert output.read_bytes() == b"historical evidence"
    generated = [path for path in output.parent.glob("*.json") if path != output]
    assert len(generated) == (0 if existing else 2)
    for path in generated:
        assert json.loads(path.read_text(encoding="utf-8-sig"))["firewall_rule_removed"] is True

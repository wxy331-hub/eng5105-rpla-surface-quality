$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$statePath = Join-Path $projectRoot 'data\output\week7_runtime\processes.json'
if (!(Test-Path -LiteralPath $statePath)) {
    Write-Output 'No Week 7 launcher state exists.'
    return
}
foreach ($entry in (Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json)) {
    $process = Get-Process -Id $entry.process_id -ErrorAction SilentlyContinue
    if ($process -and $process.StartTime.ToUniversalTime().Ticks.ToString() -eq $entry.started_ticks) {
        Stop-Process -Id $process.Id
        Write-Output "Stopped Week 7 process $($process.Id)."
    }
}

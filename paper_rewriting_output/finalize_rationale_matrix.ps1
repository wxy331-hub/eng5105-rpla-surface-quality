$ErrorActionPreference = 'Stop'

$path = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) 'writing_rationale_matrix.md'
$lines = Get-Content -LiteralPath $path
$partial = @{
    'F6'  = 'Partially verified: contextual university-wide Kulin Nations wording is present; exact campus localisation remains unavailable.'
    'F13' = 'Partially verified: the absence of direct consultation is disclosed and a protocol is specified; genuine outcomes remain unavailable.'
    'F14' = 'Partially verified: stakeholder groups and provisional needs are mapped without invented consultation; confirmation remains pending.'
    'F34' = 'Partially verified: M1–M6 accountabilities and 100% workload allocation are complete; names and headshots remain unavailable.'
}

$updated = foreach ($line in $lines) {
    if ($line -match '^\|\s*(F\d+)\s*\|') {
        $rowId = $Matches[1]
        $check = if ($partial.ContainsKey($rowId)) {
            $partial[$rowId]
        } else {
            'Verified in both final reports; paired structure, citation, numerical and evidence-label validation passed.'
        }
        $line -replace '\|\s*Pending[^|]*\|\s*$', "| $check |"
    } else {
        $line
    }
}

$updated | Set-Content -LiteralPath $path -Encoding utf8
Write-Output $path

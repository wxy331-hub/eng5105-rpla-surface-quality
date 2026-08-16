$ErrorActionPreference = 'Stop'

$outputDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$parts = @(
    'draft_front_en.md',
    'draft_functional_en.md',
    'draft_delivery_en.md'
)

$content = foreach ($part in $parts) {
    (Get-Content -LiteralPath (Join-Path $outputDir $part) -Raw).TrimEnd()
}

$target = Join-Path $outputDir 'ENG5105_Proposal_Design_Report_EN.md'
($content -join "`r`n`r`n") + "`r`n" | Set-Content -LiteralPath $target -Encoding utf8
Write-Output $target

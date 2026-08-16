$ErrorActionPreference = 'Stop'

$outputDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$parts = @(
    'draft_front_zh.md',
    'draft_functional_zh.md',
    'draft_delivery_zh.md'
)

$content = foreach ($part in $parts) {
    (Get-Content -LiteralPath (Join-Path $outputDir $part) -Raw).TrimEnd()
}

$target = Join-Path $outputDir 'ENG5105_Proposal_Design_Report_ZH.md'
($content -join "`r`n`r`n") + "`r`n" | Set-Content -LiteralPath $target -Encoding utf8
Write-Output $target

param(
    [string]$OutputDir = "D:\12591\Documents\5105\paper_rewriting_output"
)

$candidateFiles = @(
    (Join-Path $OutputDir "citation_candidates_rpla.md"),
    (Join-Path $OutputDir "citation_candidates_vision.md"),
    (Join-Path $OutputDir "citation_candidates_systems.md")
)

$rows = foreach ($file in $candidateFiles) {
    Get-Content -LiteralPath $file | Where-Object { $_ -match '^\|\s+[RVS]\d{2}\s+\|' }
}

if ($rows.Count -ne 60) {
    throw "Expected 60 citation rows; found $($rows.Count)."
}

$header = @(
    '# Citation Support Bank',
    '',
    '- Candidate target: 60 (three candidates for each of 20 intended final references).',
    '- Candidate rows present: 60.',
    '- Recent threshold: 2023-2026.',
    '- Curation rule: the final report will cite only a coherent verified subset; external results will not be transferred to this rPLA system.',
    '',
    '| Candidate ID | Reference/BibTeX | Year | Recency | Supports Section | Support Claim Sentence | Why This Paper Fits | Source | Verified | Verification Note |',
    '|---|---|---:|---|---|---|---|---|---|---|'
)

$content = ($header + $rows + @('', '## Curation status', '', 'Verification audit pending. Sources marked `yes` by the collection agents still require the automated DOI/metadata audit before final selection.', '')) -join "`r`n"
[System.IO.File]::WriteAllText((Join-Path $OutputDir 'citation_support_bank.md'), $content, [System.Text.UTF8Encoding]::new($false))

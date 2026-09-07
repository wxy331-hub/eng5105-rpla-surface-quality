<#
    Export a page range to PDF through Word, for visual checking only.

    DocStructureTags is passed as $false deliberately: with accessibility tagging
    on, exporting this document takes more than twenty minutes instead of seconds.
#>
param(
    [Parameter(Mandatory = $true)][string]$Docx,
    [Parameter(Mandatory = $true)][string]$Pdf,
    [int]$From = 1,
    [int]$To = 4
)

$Docx = (Resolve-Path $Docx).Path
# .NET keeps its own working directory, which Set-Location does not move, so a
# relative output path has to be resolved against the PowerShell location instead
$Pdf = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Pdf)

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    $doc = $word.Documents.Open($Docx, [ref]$false, [ref]$true)
    $doc.Fields.Update() | Out-Null
    $doc.TablesOfContents | ForEach-Object { $_.Update() }
    $doc.Repaginate()
    Write-Output ("pages=" + $doc.ComputeStatistics(2))
    # wdExportFormatPDF = 17, wdExportFromTo = 3, trailing $false = DocStructureTags
    $doc.ExportAsFixedFormat($Pdf, 17, $false, 0, 3, $From, $To, 0, $true, $true, 0, $true, $true, $false)
    $doc.Close([ref]$false)
} finally {
    $word.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
}
Write-Output "exported $Pdf"

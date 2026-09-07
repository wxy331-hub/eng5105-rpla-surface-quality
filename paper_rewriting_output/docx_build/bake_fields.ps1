<#
    Fill in the table of contents and save it into the file.

    Pandoc writes the contents as a TOC field with no cached result, and relies on
    the reader refreshing fields on open. Word may prompt rather than refresh, and
    WPS Office ignores the instruction altogether, so the reader sees an empty page
    where the contents should be. Opening the document once through Word, updating
    the field and saving bakes the entries and their page numbers into the file, so
    every reader sees the contents without doing anything.
#>
param([Parameter(Mandatory = $true)][string]$Docx)

$Docx = (Resolve-Path $Docx).Path

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    $doc = $word.Documents.Open($Docx, [ref]$false, [ref]$false)
    $doc.Fields.Update() | Out-Null
    $doc.TablesOfContents | ForEach-Object { $_.Update() }
    $doc.Repaginate()
    $entries = 0
    $doc.TablesOfContents | ForEach-Object { $entries += $_.Range.Paragraphs.Count }
    Write-Output ("pages=" + $doc.ComputeStatistics(2) + " toc_entries=" + $entries)
    $doc.Save()
    $doc.Close([ref]$false)
} finally {
    $word.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
}

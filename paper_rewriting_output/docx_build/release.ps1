<#
    Close any build artefact a stranded Word instance is still holding.

    bake_fields.ps1 quits Word in a finally block, but a run cut short by a closed
    pipe or a timeout can leave an instance alive with the document open, which then
    blocks the next build. This attaches to the running Word rather than killing it,
    so documents the user opened themselves are left alone.
#>
param([string]$Folder = "build")

$Folder = (Resolve-Path $Folder).Path

try {
    $word = [Runtime.InteropServices.Marshal]::GetActiveObject("Word.Application")
} catch {
    Write-Output "no running Word instance"
    exit 0
}

$closed = 0
foreach ($doc in @($word.Documents)) {
    if ($doc.Path -and $doc.Path.StartsWith($Folder, [StringComparison]::OrdinalIgnoreCase)) {
        Write-Output ("closing " + $doc.FullName)
        $doc.Close([ref]$false)
        $closed++
    }
}
Write-Output ("closed=" + $closed + " remaining=" + $word.Documents.Count)
if ($word.Documents.Count -eq 0) {
    $word.Quit()
    Write-Output "quit the empty Word instance"
}

$ErrorActionPreference = 'Stop'

$outputDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$englishPath = Join-Path $outputDir 'ENG5105_Proposal_Design_Report_EN.md'
$chinesePath = Join-Path $outputDir 'ENG5105_Proposal_Design_Report_ZH.md'

$commonReplacements = [ordered]@{
    'A$30-A$60' = 'A$30–A$60'
    'A$30-A$50' = 'A$30–A$50'
    'A$30-A$70' = 'A$30–A$70'
    'A$10-A$25' = 'A$10–A$25'
    'A$141.30-A$246.30' = 'A$141.30–A$246.30'
    'A$277.45-A$382.45' = 'A$277.45–A$382.45'
    '0-5 m/min' = '0–5 m/min'
    '+/-10 mm' = '±10 mm'
}

$english = Get-Content -LiteralPath $englishPath -Raw
foreach ($entry in $commonReplacements.GetEnumerator()) {
    $english = $english.Replace($entry.Key, $entry.Value)
}
$english = $english.Replace('Weeks 6-7', 'Weeks 6–7')
$english = $english.Replace('Weeks 7-8', 'Weeks 7–8')
$english = $english.Replace('Weeks 8-9', 'Weeks 8–9')
$english = $english.Replace('Weeks 11-12', 'Weeks 11–12')
$english = $english.Replace('Medium-High', 'Medium–High')
$english = $english.Replace('Low-Medium', 'Low–Medium')
$english | Set-Content -LiteralPath $englishPath -Encoding utf8

$chinese = Get-Content -LiteralPath $chinesePath -Raw
foreach ($entry in $commonReplacements.GetEnumerator()) {
    $chinese = $chinese.Replace($entry.Key, $entry.Value)
}
$chinese = $chinese -replace '表(?=\d)', '表 '
$chinese = $chinese -replace '图(?=\d)', '图 '
$chinese = $chinese -replace '(\d{4})年(\d{1,2})月(\d{1,2})日', '$1 年 $2 月 $3 日'
$chinese = $chinese.Replace('第3周', '第 3 周')
$chinese = $chinese.Replace('第4周', '第 4 周')
$chinese = $chinese.Replace('第5周', '第 5 周')
$chinese = $chinese.Replace('第6-7周', '第 6–7 周')
$chinese = $chinese.Replace('第7-8周', '第 7–8 周')
$chinese = $chinese.Replace('第8-9周', '第 8–9 周')
$chinese = $chinese.Replace('第10周', '第 10 周')
$chinese = $chinese.Replace('第11-12周', '第 11–12 周')
$chinese = $chinese.Replace('8月27日', '8 月 27 日')
$chinese = $chinese.Replace('目标12', '目标 12')
$chinese = $chinese.Replace('《Privacy Act》', '澳大利亚《1988 年隐私法》')
$chinese = $chinese.Replace('schema/baud/state', '模式/波特率/状态')
$chinese = $chinese.Replace('中-高', '中–高')
$chinese = $chinese.Replace('低-中', '低–中')
$chinese | Set-Content -LiteralPath $chinesePath -Encoding utf8

Write-Output $englishPath
Write-Output $chinesePath

# Queries the live model for every figure on page 02, Against Plan, for one year and comparison.
#
# The answer key is etl/comparison_expected.py, which gets the same figures from the CSVs in
# pandas. TREATAS pins the year and each button slicer the way the page does. The last block pins
# a filter-panel slicer too: an unfiltered check cannot catch a pool that ignores the panel.
#
#   powershell -File etl/verify_plan.ps1 -Year 2020 -Comparison "Budget"
#
# Run as a background job - closing the ADOMD connection can hang the shell.

param(
    [int]$Year = 2020,
    [string]$Comparison = "Budget"
)

$ErrorActionPreference = "Stop"

$msmdsrv = Get-CimInstance Win32_Process -Filter "Name='msmdsrv.exe'"
if (-not $msmdsrv) { throw "msmdsrv.exe is not running - open the PBIP in Desktop first." }
$port = $null
foreach ($proc in $msmdsrv) {
    $conn = Get-NetTCPConnection -State Listen -OwningProcess $proc.ProcessId -ErrorAction SilentlyContinue |
            Where-Object { $_.LocalAddress -eq "127.0.0.1" } | Select-Object -First 1
    if ($conn) { $port = $conn.LocalPort; break }
}
if (-not $port) { throw "could not find the local XMLA port" }

$pkg = (Get-AppxPackage -Name "*PowerBIDesktop*").InstallLocation
$adomd = @("Microsoft.PowerBI.AdomdClient.dll", "Microsoft.AnalysisServices.AdomdClient.dll") |
         ForEach-Object { Join-Path $pkg "bin\$_" } |
         Where-Object { Test-Path $_ } | Select-Object -First 1
[void][Reflection.Assembly]::LoadFrom($adomd)

$probe = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection("Data Source=localhost:$port")
$probe.Open()
$c = $probe.CreateCommand()
$c.CommandText = "SELECT [CATALOG_NAME] FROM `$SYSTEM.DBSCHEMA_CATALOGS"
$rd = $c.ExecuteReader(); $catalog = $null
if ($rd.Read()) { $catalog = $rd.GetString(0) }
$rd.Close(); $probe.Close()

$conn = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection(
    "Data Source=localhost:$port;Initial Catalog=$catalog")
$conn.Open()

function Invoke-Dax($label, $dax) {
    Write-Output ""
    Write-Output "== $label"
    $cmd = $conn.CreateCommand()
    $cmd.CommandTimeout = 300
    $cmd.CommandText = $dax
    $watch = [Diagnostics.Stopwatch]::StartNew()
    try {
        $r = $cmd.ExecuteReader()
    } catch {
        Write-Output "   FAILED: $($_.Exception.InnerException.Message)"
        return
    }
    $names = @(); for ($i = 0; $i -lt $r.FieldCount; $i++) { $names += $r.GetName($i) }
    Write-Output ("   " + ($names -join " | "))
    while ($r.Read()) {
        $vals = @()
        for ($i = 0; $i -lt $r.FieldCount; $i++) {
            $v = $r.GetValue($i)
            if ($v -is [double]) { $v = [math]::Round($v, 2) }
            $vals += "$v"
        }
        Write-Output ("   " + ($vals -join " | "))
    }
    $r.Close()
    Write-Output ("   ({0} ms)" -f $watch.ElapsedMilliseconds)
}

$pin = "TREATAS({$Year}, 'Date'[Year]), TREATAS({""$Comparison""}, 'Plan Comparison'[Comparison])"

Invoke-Dax "Headline: $Year against '$Comparison'" @"
EVALUATE
CALCULATETABLE(
    ROW(
        "Label", [Plan Comparison Label],
        "Revenue", [Revenue Actual], "Revenue comp", [Revenue Comparison], "Revenue %", [Revenue Variance %],
        "EBITDA", [EBITDA Actual], "EBITDA comp", [EBITDA Comparison], "EBITDA %", [EBITDA Variance %],
        "Net income", [Net Income Actual], "Net income comp", [Net Income Comparison],
        "EBITDA margin", [EBITDA Margin Actual], "EBITDA margin comp", [EBITDA Margin Comparison],
        "Gross margin", [Gross Margin Actual], "Gross margin comp", [Gross Margin Comparison],
        "Units ahead", [Units Ahead], "Units", [Units In Play],
        "Accounts favourable", [Accounts Favourable], "Accounts", [Accounts In Play]
    ),
    $pin
)
"@

foreach ($metric in @("Revenue", "EBITDA")) {
    Invoke-Dax "Monthly $metric" @"
EVALUATE
SUMMARIZECOLUMNS(
    'Date'[Month No], $pin, TREATAS({"$metric"}, 'Plan Chart Line'[Line]),
    "Actual", [Chart Actual], "Comparison", [Chart Comparison], "Variance", [Chart Variance]
)
ORDER BY 'Date'[Month No]
"@
}

Invoke-Dax "Business units" @"
EVALUATE
SUMMARIZECOLUMNS(
    'Business Unit'[Business Unit], $pin,
    "Actual", [EBITDA Actual], "Comparison", [EBITDA Comparison], "Variance", [EBITDA Variance],
    "Bar length", LEN([Unit EBITDA Bar]), "Pct", [Unit Variance % Label]
)
ORDER BY [Variance] DESC
"@

foreach ($show in @("Top", "Bottom")) {
    Invoke-Dax "Accounts, $show 8" @"
EVALUATE
FILTER(
    SUMMARIZECOLUMNS(
        Account[SubAccount], $pin, TREATAS({"$show"}, 'Account Ranking'[Show]),
        "Rank", [Account Effect Rank], "Actual", [Account Actual], "Comparison", [Account Comparison],
        "Effect", [Account Effect], "Pct", [Account Effect % Label]
    ),
    [Rank] <= 8
)
ORDER BY [Rank]
"@
}

Invoke-Dax "Words" @"
EVALUATE
CALCULATETABLE(
    UNION(
        ROW("Text", [Plan Standfirst]),
        ROW("Text", [Plan Title Line Chart] & " / " & [Plan Subtitle Line Chart]),
        ROW("Text", [Plan Title Variance Chart] & " / " & [Plan Subtitle Variance Chart]),
        ROW("Text", [Plan Title Unit Table] & " / " & [Plan Subtitle Unit Table]),
        ROW("Text", [Plan Title Account Table] & " / " & [Plan Subtitle Account Table]),
        ROW("Text", [Plan Filter Summary])
    ),
    $pin, TREATAS({"EBITDA"}, 'Plan Chart Line'[Line])
)
"@

Invoke-Dax "SVG cards: length and head" @"
EVALUATE
CALCULATETABLE(
    UNION(
        ROW("Card", "Revenue", "Length", LEN([Plan Card Revenue]), "Head", LEFT([Plan Card Revenue], 60)),
        ROW("Card", "EBITDA", "Length", LEN([Plan Card EBITDA]), "Head", LEFT([Plan Card EBITDA], 60)),
        ROW("Card", "Units", "Length", LEN([Plan Card Units]), "Head", LEFT([Plan Card Units], 60)),
        ROW("Card", "Accounts", "Length", LEN([Plan Card Accounts]), "Head", LEFT([Plan Card Accounts], 60))
    ),
    $pin
)
"@

Invoke-Dax "Panel slicer pinned: Region = Europe" @"
EVALUATE
CALCULATETABLE(
    ROW(
        "Units", [Units In Play], "Units ahead", [Units Ahead],
        "EBITDA", [EBITDA Actual], "EBITDA comp", [EBITDA Comparison], "Filter summary", [Plan Filter Summary]
    ),
    $pin, TREATAS({"Europe"}, 'Business Unit'[Region])
)
"@

$conn.Close()

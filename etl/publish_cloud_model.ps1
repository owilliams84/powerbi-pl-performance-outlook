# Publishes the semantic model to the Power BI Service reading its CSVs over HTTPS, so the Service
# can refresh it with no gateway.
#
#   powershell -File etl/publish_cloud_model.ps1 -WorkspaceId <guid> -ModelId <guid> -DataUrl <https folder url>
#
# -DataUrl is the folder that holds the seven CSVs somewhere private the Service can sign in to:
# the OneDrive for work or SharePoint address of data/. The dataset's licence rules out a public
# host. The repository keeps the local-path model; only a staged copy is rewritten and sent.
#
# The script sets no credentials. An organisational (OAuth2) credential set through the API is a
# bare access token that expires within the hour; signing in once in the Service stores a refresh
# token instead. After this runs: model settings > Data source credentials > Edit > OAuth2 > Sign in.
#
# Auth comes from the Azure CLI: `az login` first, as the account that owns the workspace.

param(
    [Parameter(Mandatory = $true)][string]$WorkspaceId,
    [Parameter(Mandatory = $true)][string]$ModelId,
    [Parameter(Mandatory = $true)][string]$DataUrl
)

$ErrorActionPreference = "Stop"
$ROOT = Split-Path $PSScriptRoot -Parent
$FABRIC = "https://api.fabric.microsoft.com"
$py = "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

# A fresh folder each run: a copy that came out of OneDrive can refuse to be deleted.
$staging = Join-Path $env:TEMP ("pl-cloud-model-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
& $py (Join-Path $PSScriptRoot "stage_cloud_model.py") $DataUrl $staging
if ($LASTEXITCODE -ne 0) { throw "staging failed" }
# $env:TEMP is an 8.3 short path while FullName is the long form; take the long one or Substring
# trims the wrong number of characters off every part path.
$staging = (Get-Item $staging).FullName

$parts = @()
Get-ChildItem -Path $staging -Recurse -File -Force | ForEach-Object {
    $rel = $_.FullName.Substring($staging.Length + 1).Replace('\', '/')   # the API rejects backslashes
    if ($rel -like "*.pbi/*" -or $rel -like "*cache.abf" -or $rel -like "*localSettings.json" -or $rel -eq "diagramLayout.json") { return }
    $parts += [ordered]@{ path = $rel; payload = [Convert]::ToBase64String([IO.File]::ReadAllBytes($_.FullName)); payloadType = "InlineBase64" }
}
Write-Output "$($parts.Count) parts"

$token = az account get-access-token --resource $FABRIC --query accessToken -o tsv
$headers = @{ Authorization = "Bearer $token" }

function Wait-Operation($response) {
    if ($response.StatusCode -ne 202) { return $null }
    $loc = $response.Headers["Location"]
    do { Start-Sleep 3; $st = Invoke-RestMethod -Uri $loc -Headers $headers } while ($st.status -in "Running", "NotStarted")
    if ($st.status -ne "Succeeded") { throw "operation $($st.status): $($st.error.message)" }
    return $loc
}

$body = @{ definition = @{ parts = $parts } } | ConvertTo-Json -Depth 6 -Compress
$r = Invoke-WebRequest -Method Post -Uri "$FABRIC/v1/workspaces/$WorkspaceId/semanticModels/$ModelId/updateDefinition" `
    -Headers $headers -ContentType "application/json" -Body ([Text.Encoding]::UTF8.GetBytes($body)) -UseBasicParsing
[void](Wait-Operation $r)
Write-Output "updateDefinition succeeded"

# "No error" is not evidence. Read the fact table back and look for the HTTPS source.
$r = Invoke-WebRequest -Method Post -Uri "$FABRIC/v1/workspaces/$WorkspaceId/semanticModels/$ModelId/getDefinition?format=TMDL" -Headers $headers -UseBasicParsing
$loc = Wait-Operation $r
$def = if ($loc) { Invoke-RestMethod -Uri "$loc/result" -Headers $headers } else { $r.Content | ConvertFrom-Json }
$fact = $def.definition.parts | Where-Object { $_.path -like "*tables/Financials.tmdl" }
$text = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($fact.payload))
if ($text -match "Web\.Contents" -and $text -notmatch "File\.Contents") { Write-Output "published model reads the CSVs over HTTPS" }
else { throw "the published fact table still reads a local path" }

Write-Output ""
Write-Output "Next, once, in the Service: the model's Settings > Data source credentials > Edit credentials,"
Write-Output "Authentication method OAuth2, privacy level Organizational, Sign in. Then refresh."

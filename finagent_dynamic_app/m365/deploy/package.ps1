param(
    [string]$ManifestPath = "..\packaging\manifest\manifest.dev.json",
    [string]$OutputPath = "..\packaging\dist\finagent-m365.zip"
)

if (($env:ENABLE_M365_AGENT ?? "false").ToLower() -notin @("true", "1", "yes")) {
    Write-Host "ENABLE_M365_AGENT is disabled. Skipping package build."
    exit 0
}

if (-not (Get-Command teamsapp -ErrorAction SilentlyContinue)) {
    Write-Error "The Teams/Agents Toolkit CLI ('teamsapp') is required. Install with 'npm install -g @microsoft/teamsapp-cli'."
    exit 1
}

$distFolder = Split-Path $OutputPath -Parent
if (-not (Test-Path $distFolder)) {
    New-Item -ItemType Directory -Path $distFolder | Out-Null
}

Write-Host "Packaging Microsoft 365 agent app..."
teamsapp m365agent manifest package --manifest-path $ManifestPath --output $OutputPath

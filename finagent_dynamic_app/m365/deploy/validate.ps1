param(
    [string]$ManifestPath = "..\packaging\manifest\manifest.dev.json"
)

if (($env:ENABLE_M365_AGENT ?? "false").ToLower() -notin @("true", "1", "yes")) {
    Write-Host "ENABLE_M365_AGENT is disabled. Skipping manifest validation."
    exit 0
}

if (-not (Get-Command teamsapp -ErrorAction SilentlyContinue)) {
    Write-Error "The Teams/Agents Toolkit CLI ('teamsapp') is required. Install with 'npm install -g @microsoft/teamsapp-cli'."
    exit 1
}

Write-Host "Validating Microsoft 365 agent manifest..."
teamsapp m365agent manifest validate --manifest-path $ManifestPath

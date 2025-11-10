param(
    [string]$ManifestPath = "..\packaging\manifest\manifest.dev.json"
)

if (($env:ENABLE_M365_AGENT ?? "false").ToLower() -notin @("true", "1", "yes")) {
    Write-Host "ENABLE_M365_AGENT is disabled. Skipping Copilot channel enablement."
    exit 0
}

if (-not (Get-Command teamsapp -ErrorAction SilentlyContinue)) {
    Write-Error "The Teams/Agents Toolkit CLI ('teamsapp') is required. Install with 'npm install -g @microsoft/teamsapp-cli'."
    exit 1
}

Write-Host "Enabling Microsoft 365 Copilot channel..."
teamsapp m365agent deploy copilot enable --manifest-path $ManifestPath

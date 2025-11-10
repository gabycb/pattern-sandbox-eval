# Sideloading the Microsoft 365 Agent

Follow these steps to sideload the FinAgent Dynamic autonomous experience into Microsoft Teams and enable the Microsoft 365 Copilot channel.

## 1. Prerequisites
- Install Node.js 18+ and the Microsoft 365 Agents Toolkit CLI:
  ```powershell
  npm install -g @microsoft/teamsapp-cli
  ```
- Copy `.env.m365.example` to `.env.m365` and fill in the required credentials (`ENABLE_M365_AGENT`, Entra app IDs, bot credentials, Cosmos configuration, and host URL).
- Sign in to the CLI with your Microsoft 365 developer tenant:
  ```powershell
  teamsapp account login
  ```
- Start the Microsoft 365 agent host:
  ```powershell
  cd finagent_dynamic_app\m365\host
  python app.py
  ```
  > Ensure the host is reachable from the public URL defined by `M365_HOST_BASE_URL` (Dev Tunnels or ngrok work well during development).

## 2. Validate the manifest
```powershell
cd finagent_dynamic_app\m365\deploy
./validate.ps1
```
This runs `teamsapp m365agent manifest validate` and confirms the manifest is ready.

## 3. Create the sideload package
```powershell
./package.ps1
```
The script writes a zip file to `m365/packaging/dist/finagent-m365.zip` that contains the unified manifest and icon assets.

## 4. Sideload into Microsoft Teams
```powershell
./sideload.ps1
```
This uses `teamsapp m365agent deploy sideload` to push the agent to your signed-in Teams account. You can now open the Microsoft 365 Agents Playground or Teams to test the experience.

## 5. Enable the Microsoft 365 Copilot channel
```powershell
./enable-copilot.ps1
```
This enables the Copilot channel so that the same autonomous runResearch experience is available inside Microsoft 365 Copilot.

## Troubleshooting
- All scripts exit early when `ENABLE_M365_AGENT` is not `true`.
- Use `teamsapp help` for the latest CLI switches.
- Re-run `./package.ps1` any time the manifest or icons change.
- Captured telemetry can be monitored with the existing Application Insights configuration when `OBSERVABILITY_ENABLED` is true.

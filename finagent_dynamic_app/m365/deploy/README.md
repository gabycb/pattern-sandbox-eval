# Microsoft 365 Agent Deployment Scripts

Automation wrappers around the Microsoft 365 Agents Toolkit CLI. Each script checks `ENABLE_M365_AGENT` and exits when the feature flag is disabled.

| Script | Purpose |
| --- | --- |
| `validate.ps1` | Runs `teamsapp m365agent manifest validate` on the unified manifest. |
| `package.ps1` | Produces the sideloadable `.zip` package via `teamsapp m365agent manifest package`. |
| `sideload.ps1` | Sideloads the agent into Microsoft Teams for the signed-in account. |
| `enable-copilot.ps1` | Enables the Microsoft 365 Copilot channel for the agent registration. |

## Prerequisites

- Install the CLI: `npm install -g @microsoft/teamsapp-cli`
- Provide credentials in `.env.m365`
- Sign in to the CLI before running deployment tasks: `teamsapp account login`

All scripts should be run from `finagent_dynamic_app/m365/deploy` using Windows PowerShell 5.1 or later.

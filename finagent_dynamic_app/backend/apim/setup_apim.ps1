# Automated APIM Setup Script
# This script automates the entire APIM configuration for OpenAI + Azure AI Foundry

param(
    [Parameter(Mandatory=$true)]
    [string]$SubscriptionId,
    
    [Parameter(Mandatory=$true)]
    [string]$ResourceGroup,
    
    [Parameter(Mandatory=$true)]
    [string]$ApimName,
    
    [Parameter(Mandatory=$true)]
    [string]$OpenAIResourceName,
    
    [Parameter(Mandatory=$true)]
    [string]$AIHubName,
    
    [Parameter(Mandatory=$true)]
    [string]$ProjectName
)

$ErrorActionPreference = "Stop"

Write-Host "`n╔═══════════════════════════════════════════════════════╗"
Write-Host "║   Azure APIM AI Gateway Automated Setup              ║"
Write-Host "╚═══════════════════════════════════════════════════════╝`n"

# Get access token
Write-Host "[1/10] Authenticating..."
$token = az account get-access-token --query accessToken -o tsv
$headers = @{
    Authorization = "Bearer $token"
    "Content-Type" = "application/json"
}
$baseUrl = "https://management.azure.com/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroup/providers/Microsoft.ApiManagement/service/$ApimName"

# Enable managed identity
Write-Host "[2/10] Enabling system-assigned managed identity..."
try {
    az apim update --name $ApimName --resource-group $ResourceGroup --set identity.type=SystemAssigned
    $principalId = az apim show --name $ApimName --resource-group $ResourceGroup --query identity.principalId -o tsv
    Write-Host "    ✅ Principal ID: $principalId"
} catch {
    Write-Host "    ⚠️  Identity may already exist"
    $principalId = az apim show --name $ApimName --resource-group $ResourceGroup --query identity.principalId -o tsv
}

# Assign RBAC roles
Write-Host "[3/10] Assigning RBAC roles..."

# OpenAI RBAC
$openaiScope = "/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroup/providers/Microsoft.CognitiveServices/accounts/$OpenAIResourceName"
try {
    az role assignment create --assignee $principalId --role "Cognitive Services OpenAI User" --scope $openaiScope 2>$null
    Write-Host "    ✅ OpenAI: Cognitive Services OpenAI User"
} catch {
    Write-Host "    ⚠️  OpenAI role may already exist"
}

# AI Hub RBAC
$hubScope = "/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroup/providers/Microsoft.MachineLearningServices/workspaces/$AIHubName"
try {
    az role assignment create --assignee $principalId --role "Azure AI Developer" --scope $hubScope 2>$null
    Write-Host "    ✅ Foundry: Azure AI Developer"
} catch {
    Write-Host "    ⚠️  AI Developer role may already exist"
}

try {
    az role assignment create --assignee $principalId --role "Contributor" --scope $hubScope 2>$null
    Write-Host "    ✅ Foundry: Contributor"
} catch {
    Write-Host "    ⚠️  Contributor role may already exist"
}

# Create product
Write-Host "[4/10] Creating product..."
$productBody = @{
    properties = @{
        displayName = "AI Gateway"
        description = "Unified gateway for OpenAI and Azure AI Foundry with rate limiting"
        subscriptionRequired = $true
        approvalRequired = $false
        state = "published"
    }
} | ConvertTo-Json

try {
    Invoke-RestMethod -Method Put `
        -Uri "$baseUrl/products/finagent-ai-gateway?api-version=2023-05-01-preview" `
        -Headers $headers `
        -Body $productBody | Out-Null
    Write-Host "    ✅ Product created"
} catch {
    Write-Host "    ⚠️  Product may already exist"
}

# Add product policy (rate limiting)
Write-Host "[5/10] Setting rate limiting (600 calls/60s)..."
$productPolicyXml = @"
<policies>
  <inbound>
    <rate-limit calls="600" renewal-period="60" />
    <base />
  </inbound>
  <backend>
    <base />
  </backend>
  <outbound>
    <base />
  </outbound>
  <on-error>
    <base />
  </on-error>
</policies>
"@

$policyBody = @{
    properties = @{
        value = $productPolicyXml
        format = "rawxml"
    }
} | ConvertTo-Json

Invoke-RestMethod -Method Put `
    -Uri "$baseUrl/products/finagent-ai-gateway/policies/policy?api-version=2023-05-01-preview" `
    -Headers $headers `
    -Body $policyBody | Out-Null
Write-Host "    ✅ Rate limit policy set"

# Create subscription
Write-Host "[6/10] Creating subscription..."
$subscriptionBody = @{
    properties = @{
        scope = "/products/finagent-ai-gateway"
        displayName = "AI Gateway Subscription"
        state = "active"
    }
} | ConvertTo-Json

try {
    Invoke-RestMethod -Method Put `
        -Uri "$baseUrl/subscriptions/finagent-subscription?api-version=2023-05-01-preview" `
        -Headers $headers `
        -Body $subscriptionBody | Out-Null
} catch {
    Write-Host "    ⚠️  Subscription may already exist"
}

$sub = Invoke-RestMethod -Method Post `
    -Uri "$baseUrl/subscriptions/finagent-subscription/listSecrets?api-version=2023-05-01-preview" `
    -Headers $headers

Write-Host "    ✅ Subscription Key: $($sub.primaryKey)"

# Create OpenAI API
Write-Host "[7/10] Creating OpenAI API..."
$openaiApiBody = @{
    properties = @{
        displayName = "Azure OpenAI"
        path = $OpenAIResourceName
        serviceUrl = "https://$OpenAIResourceName.openai.azure.com/openai"
        protocols = @("https")
        subscriptionRequired = $true
        subscriptionKeyParameterNames = @{
            header = "Ocp-Apim-Subscription-Key"
            query = "subscription-key"
        }
    }
} | ConvertTo-Json

Invoke-RestMethod -Method Put `
    -Uri "$baseUrl/apis/$OpenAIResourceName?api-version=2023-05-01-preview" `
    -Headers $headers `
    -Body $openaiApiBody | Out-Null

# Add OpenAI API to product
Invoke-RestMethod -Method Put `
    -Uri "$baseUrl/products/finagent-ai-gateway/apis/$OpenAIResourceName?api-version=2023-05-01-preview" `
    -Headers $headers | Out-Null

# Create OpenAI wildcard operation
$openaiOpBody = @{
    properties = @{
        displayName = "All OpenAI Operations"
        method = "*"
        urlTemplate = "/*"
    }
} | ConvertTo-Json

Invoke-RestMethod -Method Put `
    -Uri "$baseUrl/apis/$OpenAIResourceName/operations/openai-all?api-version=2023-05-01-preview" `
    -Headers $headers `
    -Body $openaiOpBody | Out-Null

# Set OpenAI policy
$openaiPolicyXml = @"
<policies>
  <inbound>
    <base />
    <authentication-managed-identity resource="https://cognitiveservices.azure.com" />
  </inbound>
  <backend>
    <base />
  </backend>
  <outbound>
    <base />
  </outbound>
  <on-error>
    <base />
  </on-error>
</policies>
"@

$policyBody = @{
    properties = @{
        value = $openaiPolicyXml
        format = "rawxml"
    }
} | ConvertTo-Json

Invoke-RestMethod -Method Put `
    -Uri "$baseUrl/apis/$OpenAIResourceName/policies/policy?api-version=2023-05-01-preview" `
    -Headers $headers `
    -Body $policyBody | Out-Null

Write-Host "    ✅ OpenAI API configured with managed identity"

# Create Foundry API
Write-Host "[8/10] Creating Azure AI Foundry API..."
$foundryApiBody = @{
    properties = @{
        displayName = "Azure AI Foundry Projects"
        path = "foundry"
        serviceUrl = "https://$AIHubName.services.ai.azure.com"
        protocols = @("https")
        subscriptionRequired = $true
        subscriptionKeyParameterNames = @{
            header = "Ocp-Apim-Subscription-Key"
            query = "subscription-key"
        }
    }
} | ConvertTo-Json

Invoke-RestMethod -Method Put `
    -Uri "$baseUrl/apis/foundry-projects?api-version=2023-05-01-preview" `
    -Headers $headers `
    -Body $foundryApiBody | Out-Null

# Add Foundry API to product
Invoke-RestMethod -Method Put `
    -Uri "$baseUrl/products/finagent-ai-gateway/apis/foundry-projects?api-version=2023-05-01-preview" `
    -Headers $headers | Out-Null

# Set Foundry policy (CRITICAL: different resource!)
$foundryPolicyXml = @"
<policies>
  <inbound>
    <base />
    <authentication-managed-identity resource="https://ai.azure.com" />
  </inbound>
  <backend>
    <base />
  </backend>
  <outbound>
    <base />
  </outbound>
  <on-error>
    <base />
  </on-error>
</policies>
"@

$policyBody = @{
    properties = @{
        value = $foundryPolicyXml
        format = "rawxml"
    }
} | ConvertTo-Json

Invoke-RestMethod -Method Put `
    -Uri "$baseUrl/apis/foundry-projects/policies/policy?api-version=2023-05-01-preview" `
    -Headers $headers `
    -Body $policyBody | Out-Null

Write-Host "    ✅ Foundry API configured with managed identity (https://ai.azure.com)"

# Create Foundry operations
Write-Host "[9/10] Creating Foundry operations..."

$operations = @(
    @{
        id = "get-assistants"
        name = "List Assistants"
        method = "GET"
        path = "/api/projects/{projectName}/assistants"
        params = @(@{ name = "projectName"; required = $true; type = "string" })
    },
    @{
        id = "update-agent"
        name = "Update Agent"
        method = "PATCH"
        path = "/api/projects/{projectName}/assistants/{assistantId}"
        params = @(
            @{ name = "projectName"; required = $true; type = "string" },
            @{ name = "assistantId"; required = $true; type = "string" }
        )
    },
    @{
        id = "create-thread"
        name = "Create Thread"
        method = "POST"
        path = "/api/projects/{projectName}/threads"
        params = @(@{ name = "projectName"; required = $true; type = "string" })
    },
    @{
        id = "create-message"
        name = "Create Message"
        method = "POST"
        path = "/api/projects/{projectName}/threads/{threadId}/messages"
        params = @(
            @{ name = "projectName"; required = $true; type = "string" },
            @{ name = "threadId"; required = $true; type = "string" }
        )
    },
    @{
        id = "list-messages"
        name = "List Messages"
        method = "GET"
        path = "/api/projects/{projectName}/threads/{threadId}/messages"
        params = @(
            @{ name = "projectName"; required = $true; type = "string" },
            @{ name = "threadId"; required = $true; type = "string" }
        )
    },
    @{
        id = "create-run"
        name = "Create Run"
        method = "POST"
        path = "/api/projects/{projectName}/threads/{threadId}/runs"
        params = @(
            @{ name = "projectName"; required = $true; type = "string" },
            @{ name = "threadId"; required = $true; type = "string" }
        )
    },
    @{
        id = "get-run"
        name = "Get Run"
        method = "GET"
        path = "/api/projects/{projectName}/threads/{threadId}/runs/{runId}"
        params = @(
            @{ name = "projectName"; required = $true; type = "string" },
            @{ name = "threadId"; required = $true; type = "string" },
            @{ name = "runId"; required = $true; type = "string" }
        )
    },
    @{
        id = "submit-tool-outputs"
        name = "Submit Tool Outputs"
        method = "POST"
        path = "/api/projects/{projectName}/threads/{threadId}/runs/{runId}/submit_tool_outputs"
        params = @(
            @{ name = "projectName"; required = $true; type = "string" },
            @{ name = "threadId"; required = $true; type = "string" },
            @{ name = "runId"; required = $true; type = "string" }
        )
    },
    @{
        id = "cancel-run"
        name = "Cancel Run"
        method = "POST"
        path = "/api/projects/{projectName}/threads/{threadId}/runs/{runId}/cancel"
        params = @(
            @{ name = "projectName"; required = $true; type = "string" },
            @{ name = "threadId"; required = $true; type = "string" },
            @{ name = "runId"; required = $true; type = "string" }
        )
    }
)

foreach ($op in $operations) {
    $opBody = @{
        properties = @{
            displayName = $op.name
            method = $op.method
            urlTemplate = $op.path
            templateParameters = $op.params
        }
    } | ConvertTo-Json -Depth 5
    
    Invoke-RestMethod -Method Put `
        -Uri "$baseUrl/apis/foundry-projects/operations/$($op.id)?api-version=2023-05-01-preview" `
        -Headers $headers `
        -Body $opBody | Out-Null
    
    Write-Host "    ✅ $($op.name)"
}

# Test configuration
Write-Host "[10/10] Testing configuration..."

$testHeaders = @{
    'Ocp-Apim-Subscription-Key' = $sub.primaryKey
}

try {
    $foundryTest = Invoke-RestMethod -Method Get `
        -Uri "https://$ApimName.azure-api.net/foundry/api/projects/$ProjectName/assistants?api-version=v1" `
        -Headers $testHeaders
    Write-Host "    ✅ Foundry: $($foundryTest.data.Count) agents accessible"
} catch {
    Write-Host "    ⚠️  Foundry test failed: $_"
}

Write-Host "`n╔═══════════════════════════════════════════════════════╗"
Write-Host "║              ✅ SETUP COMPLETE                        ║"
Write-Host "╚═══════════════════════════════════════════════════════╝`n"

Write-Host "Configuration Summary:"
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
Write-Host "APIM Gateway:        https://$ApimName.azure-api.net"
Write-Host "Subscription Key:    $($sub.primaryKey)"
Write-Host "OpenAI Endpoint:     https://$ApimName.azure-api.net/$OpenAIResourceName"
Write-Host "Foundry Endpoint:    https://$ApimName.azure-api.net/foundry/api/projects/$ProjectName"
Write-Host "Rate Limit:          600 calls per 60 seconds"
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

Write-Host "`nNext Steps:"
Write-Host "1. Update .env file with:"
Write-Host "   APIM_ENABLED=true"
Write-Host "   APIM_GATEWAY_URL=https://$ApimName.azure-api.net/$OpenAIResourceName"
Write-Host "   APIM_SUBSCRIPTION_KEY=$($sub.primaryKey)"
Write-Host "   AZURE_AI_PROJECT_ENDPOINT=https://$ApimName.azure-api.net/foundry/api/projects/$ProjectName"
Write-Host ""
Write-Host "2. Ensure your application code injects APIM headers (see apim_setup_guide.md)"
Write-Host ""

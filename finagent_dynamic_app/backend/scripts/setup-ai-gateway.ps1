param(
    [Parameter(Mandatory = $true)]
    [string]$ConfigPath,
    [switch]$SkipDiagnostics
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not (Test-Path -Path $ConfigPath)) {
    throw "Configuration file '$ConfigPath' was not found."
}

$resolvedConfig = Resolve-Path -Path $ConfigPath
$config = Get-Content -Raw -Path $resolvedConfig | ConvertFrom-Json -Depth 16
$script:InlinePolicyValues = @{}
if ($config.namedValues) {
    foreach ($nv in $config.namedValues) {
        $hasInlineFlag = $nv.PSObject.Properties.Name -contains 'inlineInPolicies'
        if ($hasInlineFlag -and $nv.inlineInPolicies -and $nv.value) {
            $script:InlinePolicyValues[$nv.name] = [string]$nv.value
        }
    }
}
$script:ArmAccessToken = $null
$script:ArmTokenExpires = Get-Date 0

function Get-SafeLabel {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value,
        [string]$Context
    )
    $replacement = $Value -replace '[^A-Za-z0-9._-]', '-'
    if ($replacement -ne $Value) {
        Write-Warning "${Context} contained unsupported characters and was sanitized to '${replacement}'."
    }
    return $replacement
}

function Get-PropertyValue {
    param(
        [Parameter(Mandatory = $false)]
        $Object,
        [Parameter(Mandatory = $true)]
        [string]$PropertyName
    )
    if (-not $Object) { return $null }
    if ($Object.PSObject.Properties.Name -contains $PropertyName) {
        return $Object.$PropertyName
    }
    return $null
}

function Wait-NamedValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [int]$Retries = 6,
        [int]$DelaySeconds = 5
    )
    for ($attempt = 1; $attempt -le $Retries; $attempt++) {
        try {
            $uri = "https://management.azure.com/subscriptions/$($config.subscriptionId)/resourceGroups/$($config.resourceGroup)/providers/Microsoft.ApiManagement/service/$($config.apimName)/namedValues/$($Name)?api-version=2023-05-01-preview"
            Invoke-ArmRest -Method "GET" -Uri $uri | Out-Null
            return
        } catch {
            if ($attempt -ge $Retries) { throw }
            Start-Sleep -Seconds $DelaySeconds
        }
    }
}

function Get-AbsoluteResourceId {
    param([string]$ResourceId)
    if (-not $ResourceId) { return $null }
    if ($ResourceId -match '^https?://') { return $ResourceId }
    if ($ResourceId.StartsWith('/')) { return "https://management.azure.com$ResourceId" }
    return $ResourceId
}

function Resolve-PolicyPlaceholders {
    param([string]$Text)
    if (-not $Text) { return $Text }
    $result = $Text
    foreach ($entry in $script:InlinePolicyValues.GetEnumerator()) {
        $token = "{{$($entry.Key)}}"
        $result = $result.Replace($token, $entry.Value)
    }
    return $result
}

function Get-ArmAccessToken {
    $now = Get-Date
    if ($script:ArmAccessToken -and $script:ArmTokenExpires -gt $now.AddMinutes(1)) {
        return $script:ArmAccessToken
    }
    $raw = Invoke-AzCli @("account", "get-access-token", "--resource", "https://management.azure.com/")
    $tokenResponse = $raw | ConvertFrom-Json
    $script:ArmAccessToken = $tokenResponse.accessToken
    try {
        $script:ArmTokenExpires = [datetime]::Parse($tokenResponse.expiresOn)
    } catch {
        $script:ArmTokenExpires = $now.AddMinutes(5)
    }
    return $script:ArmAccessToken
}

function Invoke-ArmRest {
    param(
        [Parameter(Mandatory = $true)][string]$Method,
        [Parameter(Mandatory = $true)][string]$Uri,
        [string]$Body
    )
    $token = Get-ArmAccessToken
    $headers = @{ Authorization = "Bearer $token" }
    if ($Body) { $headers["Content-Type"] = "application/json" }
    Write-Host "⇢ REST $Method $Uri" -ForegroundColor DarkCyan
    if ($Body) {
        return Invoke-RestMethod -Method $Method -Uri $Uri -Headers $headers -Body $Body -ErrorAction Stop
    } else {
        return Invoke-RestMethod -Method $Method -Uri $Uri -Headers $headers -ErrorAction Stop
    }
}

function Invoke-AzCli {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Args
    )
    $full = @("az") + $Args + @("--only-show-errors")
    Write-Host "→ $($full -join ' ')" -ForegroundColor Cyan
    return & az @Args --only-show-errors
}

function Ensure-Subscription {
    if (-not $config.subscriptionId) { throw "subscriptionId missing in config" }
    Invoke-AzCli @("account", "set", "--subscription", $config.subscriptionId)
}

function Ensure-NamedValues {
    if (-not $config.namedValues) { return }
    foreach ($nv in $config.namedValues) {
        $secret = if ($nv.secret) { "true" } else { "false" }
        $safeDisplay = Get-SafeLabel -Value $nv.displayName -Context "Named value '$($nv.name)' display name"
        $body = @{ properties = @{ displayName = $safeDisplay; secret = [bool]$nv.secret } }
        if ($nv.value) { $body.properties.value = $nv.value }
        $hasTags = $nv.PSObject.Properties.Name -contains 'tags'
        if ($hasTags -and $nv.tags) { $body.properties.tags = $nv.tags }
        $json = $body | ConvertTo-Json -Depth 10
        $uri = "https://management.azure.com/subscriptions/$($config.subscriptionId)/resourceGroups/$($config.resourceGroup)/providers/Microsoft.ApiManagement/service/$($config.apimName)/namedValues/$($nv.name)?api-version=2023-05-01-preview"
        Invoke-ArmRest -Method "PUT" -Uri $uri -Body $json | Out-Null
        Wait-NamedValue -Name $nv.name
    }
}

function Ensure-Backends {
    if (-not $config.backends) { return }
    foreach ($backend in $config.backends) {
        $body = @{ properties = @{ url = $backend.url } }
        if ($backend.protocol) { $body.properties.protocol = $backend.protocol }
        if ($backend.description) { $body.properties.description = $backend.description }
        $absoluteId = Get-AbsoluteResourceId -ResourceId $backend.resourceId
        if ($absoluteId) { $body.properties.resourceId = $absoluteId }
        $hasTls = $backend.PSObject.Properties.Name -contains 'tls'
        if ($hasTls -and $backend.tls) { $body.properties.tls = $backend.tls }
        if ($backend.identityClientId) {
            $body.properties.credentials = @{ authorization = @{ scheme = "ManagedIdentity"; parameter = $backend.identityClientId } }
        }
        $json = $body | ConvertTo-Json -Depth 10
        $uri = "https://management.azure.com/subscriptions/$($config.subscriptionId)/resourceGroups/$($config.resourceGroup)/providers/Microsoft.ApiManagement/service/$($config.apimName)/backends/$($backend.name)?api-version=2023-05-01-preview"
        Invoke-ArmRest -Method "PUT" -Uri $uri -Body $json | Out-Null
    }
}

function Publish-Fragments {
    if (-not $config.fragments) { return }
    $root = Split-Path -Parent $resolvedConfig
    foreach ($fragment in $config.fragments) {
        $path = Resolve-Path -Path (Join-Path -Path $root -ChildPath $fragment.file)
        $content = Get-Content -Raw -Path $path
        $content = Resolve-PolicyPlaceholders -Text $content
        $format = if ($fragment.format -and $fragment.format -ne "xml") { $fragment.format } else { "rawxml" }
        $body = @{ properties = @{ value = $content; format = $format } }
        if ($fragment.description) { $body.properties.description = $fragment.description }
        $fragmentJson = $body | ConvertTo-Json -Depth 32
        $uri = "https://management.azure.com/subscriptions/$($config.subscriptionId)/resourceGroups/$($config.resourceGroup)/providers/Microsoft.ApiManagement/service/$($config.apimName)/policyFragments/$($fragment.name)?api-version=2023-05-01-preview"
        Invoke-ArmRest -Method "PUT" -Uri $uri -Body $fragmentJson | Out-Null
    }
}

function Publish-Apis {
    if (-not $config.apis) { return }
    $root = Split-Path -Parent $resolvedConfig
    foreach ($api in $config.apis) {
        $policyPath = Resolve-Path -Path (Join-Path -Path $root -ChildPath $api.policyFile)
        $policy = Get-Content -Raw -Path $policyPath
        $policy = Resolve-PolicyPlaceholders -Text $policy
        $create = @(
            "apim", "api", "create",
            "--resource-group", $config.resourceGroup,
            "--service-name", $config.apimName,
            "--api-id", $api.name,
            "--path", $api.path,
            "--display-name", $api.displayName,
            "--protocols"
        ) + $api.protocols
        if ($api.serviceUrl) { $create += @("--service-url", $api.serviceUrl) }
        try {
            Invoke-AzCli $create | Out-Null
        } catch {
            $update = @(
                "apim", "api", "update",
                "--resource-group", $config.resourceGroup,
                "--service-name", $config.apimName,
                "--api-id", $api.name,
                "--path", $api.path
            )
            Invoke-AzCli $update | Out-Null
        }
        $policyBody = @{ properties = @{ value = $policy; format = "rawxml" } }
        $policyJson = $policyBody | ConvertTo-Json -Depth 10
        $uri = "https://management.azure.com/subscriptions/$($config.subscriptionId)/resourceGroups/$($config.resourceGroup)/providers/Microsoft.ApiManagement/service/$($config.apimName)/apis/$($api.name)/policies/policy?api-version=2023-05-01-preview"
        Invoke-ArmRest -Method "PUT" -Uri $uri -Body $policyJson | Out-Null
    }
}

function Ensure-Product {
    if (-not $config.product) { return }
    $prod = $config.product
    if (-not ($prod.PSObject.Properties.Name -contains 'name') -or -not $prod.name) {
        throw "config.product.name is required to create a product."
    }
    $create = @(
        "apim", "product", "create",
        "--resource-group", $config.resourceGroup,
        "--service-name", $config.apimName,
        "--product-id", $prod.name,
        "--product-name", $prod.displayName,
        "--description", $prod.description,
        "--approval-required", $prod.approvalRequired,
        "--subscriptions-limit", $prod.subscriptionsLimit,
        "--state", $prod.state
    )
    try {
        Invoke-AzCli $create | Out-Null
    } catch {
        $update = @(
            "apim", "product", "update",
            "--resource-group", $config.resourceGroup,
            "--service-name", $config.apimName,
            "--product-id", $prod.name,
            "--product-name", $prod.displayName,
            "--description", $prod.description,
            "--approval-required", $prod.approvalRequired,
            "--subscriptions-limit", $prod.subscriptionsLimit,
            "--state", $prod.state
        )
        Invoke-AzCli $update | Out-Null
    }
    if ($config.apis) {
        foreach ($api in $config.apis) {
            $link = @(
                "apim", "product", "api", "add",
                "--resource-group", $config.resourceGroup,
                "--service-name", $config.apimName,
                "--product-id", $prod.name,
                "--api-id", $api.name
            )
            Invoke-AzCli $link | Out-Null
        }
    }
        $rateLimit = $prod.rateLimit
        $rateCalls = Get-PropertyValue -Object $rateLimit -PropertyName 'calls'
        $rateRenewal = Get-PropertyValue -Object $rateLimit -PropertyName 'renewalPeriodSeconds'
        $rateKey = Get-PropertyValue -Object $rateLimit -PropertyName 'counterKey'
        if ($rateLimit -and $rateCalls -ne $null -and $rateRenewal -ne $null -and $rateKey) {
        $policy = @"
<policies>
  <inbound>
    <base />
        <rate-limit-by-key calls="${rateCalls}" renewal-period="${rateRenewal}" counter-key="${rateKey}" />
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
        $policyBody = @{ properties = @{ value = $policy; format = "rawxml" } }
        $policyJson = $policyBody | ConvertTo-Json -Depth 10
        $uri = "https://management.azure.com/subscriptions/$($config.subscriptionId)/resourceGroups/$($config.resourceGroup)/providers/Microsoft.ApiManagement/service/$($config.apimName)/products/$($prod.name)/policies/policy?api-version=2023-05-01-preview"
        Invoke-ArmRest -Method "PUT" -Uri $uri -Body $policyJson | Out-Null
    } elseif ($rateLimit) {
        Write-Warning "Product rateLimit block is incomplete; skipping policy creation."
    }
}

function Configure-Diagnostics {
    if ($SkipDiagnostics -or -not $config.diagnostics) { return }
    $diag = $config.diagnostics
    $diagName = Get-PropertyValue -Object $diag -PropertyName 'name'
    $name = if ($diagName) { $diagName } else { "gateway-logger" }
    $create = @(
        "apim", "diagnostic", "create",
        "--resource-group", $config.resourceGroup,
        "--service-name", $config.apimName,
        "--name", $name,
        "--always-log", $diag.alwaysLog,
        "--logger-id", $diag.loggerId,
        "--sampling-percentage", $diag.samplingPercentage
    )
    try {
        Invoke-AzCli $create | Out-Null
    } catch {
        $update = @(
            "apim", "diagnostic", "update",
            "--resource-group", $config.resourceGroup,
            "--service-name", $config.apimName,
            "--name", $name,
            "--always-log", $diag.alwaysLog,
            "--logger-id", $diag.loggerId,
            "--sampling-percentage", $diag.samplingPercentage
        )
        Invoke-AzCli $update | Out-Null
    }
}

Ensure-Subscription
Ensure-NamedValues
Ensure-Backends
Publish-Fragments
Publish-Apis
Ensure-Product
Configure-Diagnostics

Write-Host "AI Gateway configuration complete." -ForegroundColor Green

using System.ComponentModel.DataAnnotations;

namespace FinAgent.Backend.Infrastructure;

public class AppSettings
{
    // Azure AI / OpenAI
    public string? AzureAiProjectEndpoint { get; init; }
    public string? AzureAiModelDeploymentName { get; init; }
    public string? AzureOpenAiEndpoint { get; init; }
    public string? AzureOpenAiApiKey { get; init; }
    public string? AzureOpenAiDeployment { get; init; }
    public string AzureOpenAiApiVersion { get; init; } = "2024-08-01-preview";

    // APIM / Gateway
    public bool ApimEnabled { get; init; } = false;
    public string? ApimGatewayUrl { get; init; }
    public string? ApimSubscriptionKey { get; init; }
    public string ApimSubscriptionHeader { get; init; } = "Ocp-Apim-Subscription-Key";

    // APIM diagnostics (optional)
    public string? ApimLogAnalyticsWorkspaceId { get; init; }
    public string? ApimApplicationInsightsKey { get; init; }
    public bool ApimDebugMode { get; init; } = false;
    public bool ApimLogRequestBody { get; init; } = false;
    public bool ApimLogResponseBody { get; init; } = false;

    public bool ApimEnableLoadBalancing { get; init; } = true;
    public bool ApimEnableRateLimiting { get; init; } = true;
    public bool ApimEnableContentFiltering { get; init; } = true;
    public bool ApimEnableTokenTracking { get; init; } = true;
    public bool ApimEnableCaching { get; init; } = false;

    // Financial Data APIs
    public string? FmpApiKey { get; init; }
    public string? DcfApiKey { get; init; }
    public bool YahooFinanceEnabled { get; init; } = true;
    public string YahooFinanceMcpUrl { get; init; } = "http://localhost:8001/sse";
    public string? SecApiKey { get; init; }
    public string SecUserAgent { get; init; } = "FinAgent Research Bot contact@example.com";

    // Storage
    public string? AzureStorageConnectionString { get; init; }
    public string AzureStorageContainer { get; init; } = "financial-reports";

    // Chat / Web PubSub
    public bool EnableChatAutorun { get; init; } = true;
    public string? WebPubSubConnectionString { get; init; }
    public string WebPubSubHub { get; init; } = "finagent_chat";

    // Cosmos
    public string? CosmosDbEndpoint { get; init; }
    public string? CosmosDbKey { get; init; }
    public string CosmosDbDatabase { get; init; } = "finagent";
    public string CosmosDbContainer { get; init; } = "dynamic";

    // Auth
    public string? AzureTenantId { get; init; }
    public string? AzureClientId { get; init; }
    public string? AzureClientSecret { get; init; }

    // Backend
    public string BackendHost { get; init; } = "0.0.0.0";
    public int BackendPort { get; init; } = 8000;
    public string CorsOrigins { get; init; } = "http://localhost:5173,http://localhost:3000";

    // Observability
    public bool ObservabilityEnabled { get; init; } = false;
    public string? ObservabilityOtlpEndpoint { get; init; }
    public bool ObservabilityEnableSensitiveData { get; init; } = false;
    public bool EnableApplicationInsightsExport { get; init; } = false;
    public string? ApplicationInsightsConnectionString { get; init; }

    // Agent
    public int MaxConcurrentAgents { get; init; } = 5;
    public int DefaultAgentTimeout { get; init; } = 300;
    public bool EnableAgentTelemetry { get; init; } = false;
    public bool EnableAgentThreads { get; init; } = false;
    public bool EnableAgentConversations { get; init; } = false;

    // M365
    public bool EnableM365Agent { get; init; } = false;
    public string? M365HostBaseUrl { get; init; }
    public string? M365ClientId { get; init; }
    public string? M365ClientSecret { get; init; }
    public string? M365TenantId { get; init; }
    public string? M365BotId { get; init; }
    public string? M365BotPassword { get; init; }

    public IEnumerable<string> CorsOriginsList => (CorsOrigins ?? string.Empty)
        .Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
}

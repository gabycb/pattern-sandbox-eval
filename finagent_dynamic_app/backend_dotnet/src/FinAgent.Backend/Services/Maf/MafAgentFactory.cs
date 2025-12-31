using System.Net.Http;
using Azure.AI.Agents.Persistent;
using Azure.Core;
using Azure.Identity;
using FinAgent.Backend.Infrastructure;
using FinAgent.Backend.Services.Maf.Agents;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace FinAgent.Backend.Services.Maf;

public interface IMafAgentFactory
{
    bool Enabled { get; }
    Task<object?> GetOrCreateAsync(string name, CancellationToken ct = default);
    IReadOnlyCollection<string> RegisteredAgents { get; }
    AgentDefinition? GetDefinition(string name);
}

public sealed class NullMafAgentFactory : IMafAgentFactory
{
    public bool Enabled => false;
    public IReadOnlyCollection<string> RegisteredAgents => Array.Empty<string>();
    public Task<object?> GetOrCreateAsync(string name, CancellationToken ct = default) => Task.FromResult<object?>(null);
    public AgentDefinition? GetDefinition(string name) => null;
}

public sealed class MafAgentFactory : IMafAgentFactory
{
    private readonly PersistentAgentsClient _agentsClient = null!;
    private readonly string _rawEndpoint;
    private readonly ILogger<MafAgentFactory> _logger;
    private readonly ILoggerFactory _loggerFactory;
    private readonly string _modelDeployment;
    private readonly Dictionary<string, AgentDefinition> _definitions = new(StringComparer.OrdinalIgnoreCase);
    private readonly Dictionary<string, object> _cache = new(StringComparer.OrdinalIgnoreCase);
    private readonly bool _enabled = true;
    private readonly AppSettings _settings;
    private readonly HttpClient _httpClient = new();
    private readonly FmpClient _fmpClient;
    private readonly IAzureOpenAIService _llmService;

    public MafAgentFactory(IOptions<AppSettings> settings, ILogger<MafAgentFactory> logger, ILoggerFactory loggerFactory, IAzureOpenAIService llmService)
    {
        var cfg = settings.Value;
        _settings = cfg;
        _loggerFactory = loggerFactory;
        _llmService = llmService;
        _fmpClient = new FmpClient(_httpClient, cfg.FmpApiKey ?? string.Empty, logger);
        if (string.IsNullOrWhiteSpace(cfg.AzureAiProjectEndpoint) || string.IsNullOrWhiteSpace(cfg.AzureAiModelDeploymentName))
        {
            throw new InvalidOperationException("Azure AI project configuration is required for Microsoft Agent Framework.");
        }

        _logger = logger;
        _modelDeployment = cfg.AzureAiModelDeploymentName!;
        var credential = BuildCredential(cfg);
        _rawEndpoint = cfg.ApimEnabled && !string.IsNullOrWhiteSpace(cfg.ApimGatewayUrl)
            ? cfg.ApimGatewayUrl!
            : cfg.AzureAiProjectEndpoint!;

        if (!TryParseEndpoint(_rawEndpoint, out var endpointUri))
        {
            _enabled = false;
            _logger.LogWarning("MAF agent factory disabled: AzureAiProjectEndpoint must be a connection string (<endpoint>;<subscription_id>;<resource_group_name>;<project_name>) or an endpoint URL.");
            return;
        }

        try
        {
            _agentsClient = new PersistentAgentsClient(endpointUri.ToString(), credential);
        }
        catch (Exception ex)
        {
            _enabled = false;
            _logger.LogError(ex, "Failed to initialize PersistentAgentsClient for endpoint {Endpoint}", endpointUri);
            return;
        }

        RegisterDefaults();
    }

    public bool Enabled => _enabled;

    public IReadOnlyCollection<string> RegisteredAgents => _enabled ? _definitions.Keys : Array.Empty<string>();

    public AgentDefinition? GetDefinition(string name)
    {
        if (!_enabled) return null;
        return _definitions.TryGetValue(name, out var def) ? def : null;
    }

    public async Task<object?> GetOrCreateAsync(string name, CancellationToken ct = default)
    {
        if (!_enabled)
        {
            _logger.LogWarning("MAF agent factory disabled; cannot resolve {Agent}", name);
            return null;
        }

        if (!_definitions.TryGetValue(name, out var def))
        {
            _logger.LogWarning("Agent definition not found for {Agent}", name);
            return null;
        }

        if (_cache.TryGetValue(name, out var cached))
        {
            return cached;
        }

        // Custom runtime agents (full parity implemented in .NET)
        if (name.Equals(CompanyAgent.Name, StringComparison.OrdinalIgnoreCase))
        {
            var runtime = new CompanyAgentRuntime(_fmpClient, _settings, _llmService, _loggerFactory.CreateLogger<CompanyAgentRuntime>());
            _cache[name] = runtime;
            return runtime;
        }

        if (name.Equals(SECAgent.Name, StringComparison.OrdinalIgnoreCase))
        {
            var runtime = new SECAgentRuntime(_fmpClient, _llmService, _loggerFactory.CreateLogger<SECAgentRuntime>());
            _cache[name] = runtime;
            return runtime;
        }

        if (name.Equals(EarningCallAgent.Name, StringComparison.OrdinalIgnoreCase))
        {
            var runtime = new EarningsAgentRuntime(_fmpClient, _llmService, _loggerFactory.CreateLogger<EarningsAgentRuntime>());
            _cache[name] = runtime;
            return runtime;
        }

        if (name.Equals(FundamentalsAgent.Name, StringComparison.OrdinalIgnoreCase))
        {
            var runtime = new FundamentalsAgentRuntime(_fmpClient, _llmService, _loggerFactory.CreateLogger<FundamentalsAgentRuntime>());
            _cache[name] = runtime;
            return runtime;
        }

        if (name.Equals(TechnicalsAgent.Name, StringComparison.OrdinalIgnoreCase))
        {
            var runtime = new TechnicalsAgentRuntime(_llmService, _loggerFactory.CreateLogger<TechnicalsAgentRuntime>());
            _cache[name] = runtime;
            return runtime;
        }

        if (name.Equals(ForecasterAgent.Name, StringComparison.OrdinalIgnoreCase))
        {
            var runtime = new ForecasterAgentRuntime(_llmService, _loggerFactory.CreateLogger<ForecasterAgentRuntime>());
            _cache[name] = runtime;
            return runtime;
        }

        if (name.Equals(SummarizerAgent.Name, StringComparison.OrdinalIgnoreCase))
        {
            var runtime = new SummarizerAgentRuntime(_llmService, _loggerFactory.CreateLogger<SummarizerAgentRuntime>());
            _cache[name] = runtime;
            return runtime;
        }

        if (name.Equals(ReportAgent.Name, StringComparison.OrdinalIgnoreCase))
        {
            var runtime = new ReportAgentRuntime(_llmService, _loggerFactory.CreateLogger<ReportAgentRuntime>());
            _cache[name] = runtime;
            return runtime;
        }

        try
        {
            var agent = await _agentsClient.CreateAIAgentAsync(
                model: def.ModelDeployment ?? _modelDeployment,
                name: def.TypeName,
                description: def.Description,
                instructions: def.SystemPrompt,
                cancellationToken: ct).ConfigureAwait(false);

            _logger.LogInformation("Created Azure AI agent {Agent}", name);
            _cache[name] = agent;
            return agent;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to build Azure AI agent {Agent}", name);
            return null;
        }
    }

    private void RegisterDefaults()
    {
        foreach (var definition in AgentCatalog.All)
        {
            _definitions[definition.TypeName] = definition;
        }
    }

    private static TokenCredential BuildCredential(AppSettings cfg)
    {
        if (!string.IsNullOrWhiteSpace(cfg.AzureTenantId) &&
            !string.IsNullOrWhiteSpace(cfg.AzureClientId) &&
            !string.IsNullOrWhiteSpace(cfg.AzureClientSecret))
        {
            return new ClientSecretCredential(cfg.AzureTenantId, cfg.AzureClientId, cfg.AzureClientSecret);
        }

        return new DefaultAzureCredential(new DefaultAzureCredentialOptions
        {
            ExcludeInteractiveBrowserCredential = true
        });
    }

    private static bool TryParseEndpoint(string rawEndpoint, out Uri endpoint)
    {
        endpoint = null!;
        if (string.IsNullOrWhiteSpace(rawEndpoint))
        {
            return false;
        }

        var parts = rawEndpoint.Split(';', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        var endpointText = parts.Length >= 4
            ? $"{parts[0].TrimEnd('/')}/api/projects/{parts[3]}"
            : (parts.Length > 0 ? parts[0] : rawEndpoint);
        if (Uri.TryCreate(endpointText, UriKind.Absolute, out var parsed))
        {
            endpoint = parsed;
            return true;
        }

        return false;
    }
}

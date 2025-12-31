using Azure;
using Azure.AI.OpenAI;
using Azure.Identity;
using FinAgent.Backend.Infrastructure;
using Microsoft.Extensions.Options;
using OpenAI.Chat;

namespace FinAgent.Backend.Services;

public interface IAzureOpenAIService
{
    Task<string> CompleteAsync(string systemPrompt, string userPrompt, CancellationToken ct = default);
}

public sealed class AzureOpenAIService : IAzureOpenAIService
{
    private readonly ChatClient _chatClient;
    private readonly ILogger<AzureOpenAIService> _logger;

    public AzureOpenAIService(IOptions<AppSettings> settings, ILogger<AzureOpenAIService> logger)
    {
        _logger = logger;
        var cfg = settings.Value;

        if (string.IsNullOrWhiteSpace(cfg.AzureOpenAiEndpoint) || string.IsNullOrWhiteSpace(cfg.AzureOpenAiDeployment))
        {
            throw new InvalidOperationException("AzureOpenAiEndpoint and AzureOpenAiDeployment must be configured");
        }

        AzureOpenAIClient azureClient;
        if (!string.IsNullOrWhiteSpace(cfg.AzureOpenAiApiKey))
        {
            azureClient = new AzureOpenAIClient(new Uri(cfg.AzureOpenAiEndpoint), new AzureKeyCredential(cfg.AzureOpenAiApiKey));
            _logger.LogInformation("Azure OpenAI client initialized with API key");
        }
        else
        {
            azureClient = new AzureOpenAIClient(new Uri(cfg.AzureOpenAiEndpoint), new DefaultAzureCredential());
            _logger.LogInformation("Azure OpenAI client initialized with DefaultAzureCredential");
        }

        _chatClient = azureClient.GetChatClient(cfg.AzureOpenAiDeployment);
    }

    public async Task<string> CompleteAsync(string systemPrompt, string userPrompt, CancellationToken ct = default)
    {
        try
        {
            var messages = new List<ChatMessage>
            {
                new SystemChatMessage(systemPrompt),
                new UserChatMessage(userPrompt)
            };

            var response = await _chatClient.CompleteChatAsync(messages, cancellationToken: ct);
            return response.Value.Content[0].Text;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error calling Azure OpenAI");
            return $"Error: {ex.Message}";
        }
    }
}

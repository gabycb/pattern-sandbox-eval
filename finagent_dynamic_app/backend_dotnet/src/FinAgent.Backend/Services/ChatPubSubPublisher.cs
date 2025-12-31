using System.Text.Json;
using System.Text.Json.Serialization;
using Azure.Messaging.WebPubSub;
using FinAgent.Backend.Infrastructure;
using FinAgent.Backend.Models;
using Microsoft.Extensions.Options;

namespace FinAgent.Backend.Services;

/// <summary>
/// Azure Web PubSub publisher for streaming chat/plan events.
/// Falls back to no-op when no connection string is provided.
/// </summary>
public class ChatPubSubPublisher
{
    private readonly WebPubSubServiceClient? _client;
    private readonly string _hub;
    private readonly JsonSerializerOptions _jsonOptions;
    private readonly ILogger<ChatPubSubPublisher> _logger;

    public ChatPubSubPublisher(IOptions<AppSettings> settings, ILogger<ChatPubSubPublisher> logger)
    {
        _logger = logger;
        var cfg = settings.Value;
        _hub = cfg.WebPubSubHub;
        _jsonOptions = new JsonSerializerOptions
        {
            PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
            DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull
        };
        _jsonOptions.Converters.Add(new JsonStringEnumConverter(JsonNamingPolicy.CamelCase));

        if (!string.IsNullOrWhiteSpace(cfg.WebPubSubConnectionString))
        {
            _client = new WebPubSubServiceClient(cfg.WebPubSubConnectionString, _hub);
            _logger.LogInformation("Web PubSub client initialized for hub {Hub}", _hub);
        }
        else
        {
            _logger.LogWarning("Web PubSub disabled - no connection string configured");
        }
    }

    public bool IsEnabled => _client is not null;

    public Task<Dictionary<string, string>?> GetClientAccessAsync(string userId, string taskId, CancellationToken ct = default)
    {
        if (_client is null) return Task.FromResult<Dictionary<string, string>?>(null);
        var group = Group(taskId);
        var uri = _client.GetClientAccessUri(
            userId: userId,
            roles: new[] { "webpubsub.joinLeaveGroup" },
            groups: new[] { group });

        return Task.FromResult<Dictionary<string, string>?>(new()
        {
            ["url"] = uri.AbsoluteUri,
            ["group"] = group
        });
    }

    public async Task SendEventAsync(ChatEventPayload payload, CancellationToken ct = default)
    {
        if (_client is null)
        {
            _logger.LogDebug("WebPubSub disabled; skipping event {Type}", payload.Type);
            return;
        }

        var group = Group(payload.TaskId);
        var json = JsonSerializer.Serialize(payload, _jsonOptions);

        _logger.LogInformation("Sending WebPubSub event {Type} to group {Group}", payload.Type, group);

        await _client.SendToGroupAsync(group, json);
    }

    private string Group(string taskId) => $"task:{taskId}";
}

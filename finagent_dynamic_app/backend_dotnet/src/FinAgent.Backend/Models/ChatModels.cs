using System.Text.Json.Serialization;

namespace FinAgent.Backend.Models;

public record ChatObjectiveRequest
{
    [JsonPropertyName("objective")] public required string Objective { get; init; }
    [JsonPropertyName("ticker")] public string? Ticker { get; init; }
    [JsonPropertyName("scope")] public IEnumerable<string>? Scope { get; init; }
    [JsonPropertyName("session_id")] public string? SessionId { get; init; }
}

public record ChatObjectiveResponse
{
    public required string TaskId { get; init; }
    public required string SessionId { get; init; }
    public required PlanWithSteps Plan { get; init; }
    public string? WebPubSubUrl { get; init; }
    public string? WebPubSubGroup { get; init; }
}

public record ChatConfigResponse
{
    public required bool Enabled { get; init; }
}

public record StepPatch
{
    public required string Id { get; init; }
    public string? Action { get; init; }
    public string? HumanFeedback { get; init; }
}

public record ChatConfirmRequest
{
    public required string TaskId { get; init; }
    public string? SessionId { get; init; }
    public string Action { get; init; } = "continue"; // continue | modify
    public IEnumerable<StepPatch>? Steps { get; init; }
}

public record ChatConfirmResponse
{
    public required string TaskId { get; init; }
    public required string SessionId { get; init; }
    public required PlanWithSteps Plan { get; init; }
}

public record ChatCancelRequest
{
    public required string TaskId { get; init; }
    public string? SessionId { get; init; }
}

public record StartChatRequest
{
    public required string TaskId { get; init; }
    public required string SessionId { get; init; }
}

public record StartChatResponse
{
    public required string TaskId { get; init; }
    public required string SessionId { get; init; }
    public required string Status { get; init; }
}

public record StopChatRequest
{
    public required string TaskId { get; init; }
    public required string SessionId { get; init; }
}

public record ChatStatusResponse
{
    public required string TaskId { get; init; }
    public required string SessionId { get; init; }
    public required PlanWithSteps Plan { get; init; }
    public required IReadOnlyList<AgentMessage> Messages { get; init; }
    public DateTime UpdatedAt { get; init; } = DateTime.UtcNow;
}

public record ChatEventPayload
{
    public required string Type { get; init; }
    public required string TaskId { get; init; }
    public required string SessionId { get; init; }
    public required IDictionary<string, object> Data { get; init; }
    public DateTime Timestamp { get; init; } = DateTime.UtcNow;
}

public record ChatRunSnapshot
{
    public required PlanWithSteps Plan { get; init; }
    public required IReadOnlyList<AgentMessage> Messages { get; init; }
}

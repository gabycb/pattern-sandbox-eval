using System.Text.Json.Serialization;

namespace FinAgent.Backend.Models;

public enum DataType
{
    Session,
    Plan,
    Step,
    Message
}

public enum AgentType
{
    Planner_Agent,
    Company_Agent,
    SEC_Agent,
    EarningCall_Agent,
    Fundamentals_Agent,
    Technicals_Agent,
    Forecaster_Agent,
    Report_Agent,
    Summarizer_Agent,
    Ticker_Extraction_Agent,
    Generic_Agent,
    Human_Agent,
    GroupChatManager
}

public enum StepStatus
{
    Planned,
    Awaiting_Feedback,
    Approved,
    Rejected,
    Action_Requested,
    Executing,
    Completed,
    Failed
}

public enum PlanStatus
{
    In_Progress,
    Completed,
    Failed,
    Cancelled
}

public enum HumanFeedbackStatus
{
    Requested,
    Accepted,
    Rejected
}

public record BaseDataModel
{
    public string Id { get; init; } = Guid.NewGuid().ToString();
    public DateTime Timestamp { get; init; } = DateTime.UtcNow;
}

public record Session : BaseDataModel
{
    [JsonPropertyName("data_type")] public DataType DataType { get; init; } = DataType.Session;
    public required string SessionId { get; init; }
    public required string UserId { get; init; }
    public DateTime CreatedAt { get; init; } = DateTime.UtcNow;
    public DateTime LastActive { get; init; } = DateTime.UtcNow;
    public IDictionary<string, object>? Metadata { get; init; }
}

public record Plan : BaseDataModel
{
    [JsonPropertyName("data_type")] public DataType DataType { get; init; } = DataType.Plan;
    public required string SessionId { get; init; }
    public required string UserId { get; init; }
    public required string InitialGoal { get; init; }
    public string? Summary { get; init; }
    public PlanStatus OverallStatus { get; set; } = PlanStatus.In_Progress;
    public string? HumanClarificationRequest { get; init; }
    public string? HumanClarificationResponse { get; set; }
    public int TotalSteps { get; set; }
    public int CompletedSteps { get; set; }
    public int FailedSteps { get; set; }
    public string? Ticker { get; init; }
    public IEnumerable<string>? Scope { get; init; }
}

public record Step : BaseDataModel
{
    [JsonPropertyName("data_type")] public DataType DataType { get; init; } = DataType.Step;
    public required string PlanId { get; init; }
    public required string SessionId { get; init; }
    public required string UserId { get; init; }
    public required string Action { get; set; }
    public AgentType Agent { get; init; }
    public StepStatus Status { get; set; } = StepStatus.Planned;
    public string? AgentReply { get; set; }
    public string? ErrorMessage { get; set; }
    public string? HumanFeedback { get; set; }
    public HumanFeedbackStatus HumanApprovalStatus { get; set; } = HumanFeedbackStatus.Requested;
    public string? UpdatedAction { get; set; }
    public int? Order { get; set; }
    public bool ManuallyInjected { get; init; } = false;
    public List<string> Dependencies { get; init; } = new();
    public List<string> RequiredArtifacts { get; init; } = new();
    public List<string> Tools { get; init; } = new();
}

public record AgentMessage : BaseDataModel
{
    [JsonPropertyName("data_type")] public DataType DataType { get; init; } = DataType.Message;
    public required string SessionId { get; init; }
    public required string UserId { get; init; }
    public required string PlanId { get; init; }
    public string? StepId { get; init; }
    public required string Content { get; init; }
    public required string Source { get; init; }
    public string? Target { get; init; }
    public string? MessageType { get; init; }
    public IDictionary<string, object>? Metadata { get; init; }
}

public record InputTask
{
    public string? SessionId { get; set; }
    public string? UserId { get; set; }
    public required string Description { get; set; }
    public string? Ticker { get; set; }
    public IEnumerable<string>? Scope { get; set; }
    public string? Depth { get; set; }
}

public record HumanFeedback
{
    public string? StepId { get; set; }
    public required string PlanId { get; set; }
    public required string SessionId { get; set; }
    public required bool Approved { get; set; }
    public string? HumanFeedbackText { get; set; }
    public string? UpdatedAction { get; set; }
}

public record ActionResponse
{
    public required string StepId { get; init; }
    public required string PlanId { get; init; }
    public required string SessionId { get; init; }
    public bool Success { get; init; }
    public string? Result { get; init; }
    public string? Error { get; init; }
    public IDictionary<string, object>? Metadata { get; init; }
}

public record PlanWithSteps
{
    public required string Id { get; init; }
    public required string SessionId { get; init; }
    public required string UserId { get; init; }
    public required string InitialGoal { get; init; }
    public string? Summary { get; init; }
    public PlanStatus OverallStatus { get; init; }
    public string? HumanClarificationRequest { get; init; }
    public string? HumanClarificationResponse { get; init; }
    public int TotalSteps { get; init; }
    public int CompletedSteps { get; init; }
    public int FailedSteps { get; init; }
    public DateTime Timestamp { get; init; }
    public string? Ticker { get; init; }
    public IEnumerable<string>? Scope { get; init; }
    public List<Step> Steps { get; init; } = new();
    public int StepsRequiringApproval { get; init; }
    public int Completed { get; init; }
}

public record TaskListItem
{
    public required string Id { get; init; }
    public required string SessionId { get; init; }
    public required string InitialGoal { get; init; }
    public PlanStatus OverallStatus { get; init; }
    public int TotalSteps { get; init; }
    public int CompletedSteps { get; init; }
    public DateTime Timestamp { get; init; }
    public string? Ticker { get; init; }
}

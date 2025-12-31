using System.Linq;
using System.Text;
using FinAgent.Backend.Infrastructure;
using FinAgent.Backend.Models;
using FinAgent.Backend.Services.Maf;
using Microsoft.Extensions.Options;

namespace FinAgent.Backend.Services;

/// <summary>
/// Lightweight orchestrator placeholder to preserve API surface. Replaces full Agent Framework orchestration
/// with simplified in-memory behavior suitable for parity testing. Actual agent execution should be added later.
/// </summary>
public class TaskOrchestrator
{
    private readonly ICosmosMemoryStore _store;
    private readonly AppSettings _settings;
    private readonly MafDynamicPlanner _planner;
    private readonly IMafAgentFactory _mafFactory;

    public TaskOrchestrator(ICosmosMemoryStore store, IOptions<AppSettings> settings, MafDynamicPlanner planner, IMafAgentFactory mafFactory)
    {
        _store = store;
        _settings = settings.Value;
        _planner = planner;
        _mafFactory = mafFactory;
    }

    public async Task InitializeAsync(CancellationToken ct = default)
    {
        // Placeholder; real implementation would warm up Agent Framework clients and Cosmos.
        await Task.CompletedTask;
    }

    public Task ShutdownAsync(CancellationToken ct = default) => Task.CompletedTask;

    public ICosmosMemoryStore Store => _store;

    public async Task<PlanWithSteps> CreatePlanFromObjectiveAsync(InputTask input, string userId, CancellationToken ct = default)
    {
        var sessionId = input.SessionId ?? $"session-{Guid.NewGuid():N}";
        var planId = $"plan-{Guid.NewGuid():N}";
        var session = new Session
        {
            SessionId = sessionId,
            UserId = userId,
            Metadata = new Dictionary<string, object>
            {
                ["objective"] = input.Description,
                ["ticker"] = input.Ticker ?? string.Empty
            }
        };
        await _store.CreateSessionAsync(session, ct);

        var plannedSteps = await BuildPlannedStepsAsync(input, planId, sessionId, userId, ct);
        if (!plannedSteps.Any())
        {
            // Fallback single step for resilience
            plannedSteps.Add(new Step
            {
                PlanId = planId,
                SessionId = sessionId,
                UserId = userId,
                Action = input.Description,
                Agent = AgentType.Company_Agent,
                Status = StepStatus.Planned,
                Order = 1
            });
        }

        var plan = new Plan
        {
            Id = planId,
            SessionId = sessionId,
            UserId = userId,
            InitialGoal = input.Description,
            Summary = null,
            OverallStatus = PlanStatus.In_Progress,
            Ticker = input.Ticker,
            Scope = input.Scope,
            TotalSteps = plannedSteps.Count,
            CompletedSteps = plannedSteps.Count(s => s.Status == StepStatus.Completed),
            FailedSteps = plannedSteps.Count(s => s.Status == StepStatus.Failed),
            Timestamp = DateTime.UtcNow
        };

        await _store.AddPlanAsync(plan, ct);
        foreach (var step in plannedSteps)
        {
            await _store.AddStepAsync(step, ct);
        }

        return new PlanWithSteps
        {
            Id = plan.Id,
            SessionId = sessionId,
            UserId = userId,
            InitialGoal = plan.InitialGoal,
            Summary = plan.Summary,
            OverallStatus = plan.OverallStatus,
            HumanClarificationRequest = plan.HumanClarificationRequest,
            HumanClarificationResponse = plan.HumanClarificationResponse,
            TotalSteps = plan.TotalSteps,
            CompletedSteps = plan.CompletedSteps,
            FailedSteps = plan.FailedSteps,
            Timestamp = plan.Timestamp,
            Ticker = plan.Ticker,
            Scope = plan.Scope,
            Steps = plannedSteps,
            StepsRequiringApproval = plannedSteps.Count,
            Completed = plannedSteps.Count(s => s.Status == StepStatus.Completed)
        };
    }

    private async Task<List<Step>> BuildPlannedStepsAsync(InputTask input, string planId, string sessionId, string userId, CancellationToken ct)
    {
        if (!_planner.Enabled)
        {
            return new List<Step>();
        }

        var steps = await _planner.GeneratePlanAsync(input, ct).ConfigureAwait(false);
        return steps.Select(step => new Step
        {
            PlanId = planId,
            SessionId = sessionId,
            UserId = userId,
            Action = step.Action,
            Agent = MapAgent(step.Agent),
            Status = StepStatus.Planned,
            Order = step.Order,
            Tools = step.Parameters.TryGetValue("tools", out var toolsObj) && toolsObj is IEnumerable<string> tools
                ? tools.ToList()
                : (step.Tool is null ? new List<string>() : new List<string> { step.Tool }),
            HumanFeedback = input.Description
        }).ToList();
    }

    private async Task<ExecutionResult> ExecuteStepAsync(Step step, CancellationToken ct)
    {
        var agentName = AgentTypeToName(step.Agent);
        var agent = await _mafFactory.GetOrCreateAsync(agentName, ct).ConfigureAwait(false);
        if (agent is null)
        {
            return new ExecutionResult(false, "Agent unavailable", "Agent not found");
        }

        var plan = await _store.GetPlanAsync(step.PlanId, step.SessionId, ct).ConfigureAwait(false);
        var prompt = await BuildStepPromptAsync(step, plan, ct).ConfigureAwait(false);

        string messageText;
        try
        {
            dynamic dynAgent = agent;
            var response = await dynAgent.RunAsync(prompt, cancellationToken: ct);
            messageText = ExtractText(response);
            if (string.IsNullOrWhiteSpace(messageText))
            {
                messageText = "No response produced.";
            }
        }
        catch (Exception ex)
        {
            return new ExecutionResult(false, "", ex.Message);
        }

        var agentMessage = new AgentMessage
        {
            PlanId = step.PlanId,
            SessionId = step.SessionId,
            UserId = step.UserId,
            StepId = step.Id,
            Content = messageText,
            Source = agentName,
            Target = null,
            MessageType = "agent_response",
            Metadata = new Dictionary<string, object>
            {
                ["agent"] = agentName,
                ["tools"] = step.Tools,
                ["order"] = step.Order ?? 0,
                ["action"] = step.Action
            }
        };

        await _store.AddMessageAsync(agentMessage, ct);

        return new ExecutionResult(true, messageText, null);
    }

    private static string ExtractText(dynamic response)
    {
        try
        {
            if (response is null) return string.Empty;
            if (response.Text is string text) return text;
        }
        catch
        {
            // ignored
        }

        try
        {
            return response.ToString();
        }
        catch
        {
            return string.Empty;
        }
    }

    private static AgentType MapAgent(string agent)
    {
        return agent switch
        {
            "Planner_Agent" => AgentType.Planner_Agent,
            "Company_Agent" => AgentType.Company_Agent,
            "SEC_Agent" => AgentType.SEC_Agent,
            "Earnings_Agent" or "EarningCall_Agent" => AgentType.EarningCall_Agent,
            "Fundamentals_Agent" => AgentType.Fundamentals_Agent,
            "Technicals_Agent" => AgentType.Technicals_Agent,
            "Forecaster_Agent" => AgentType.Forecaster_Agent,
            "Report_Agent" => AgentType.Report_Agent,
            "Summarizer_Agent" => AgentType.Summarizer_Agent,
            "Ticker_Extraction_Agent" or "TickerExtraction_Agent" or "ticker_extraction" => AgentType.Ticker_Extraction_Agent,
            _ => AgentType.Generic_Agent
        };
    }

    private static string AgentTypeToName(AgentType agent) => agent switch
    {
        AgentType.Planner_Agent => "Planner_Agent",
        AgentType.Company_Agent => "Company_Agent",
        AgentType.SEC_Agent => "SEC_Agent",
        AgentType.EarningCall_Agent => "EarningCall_Agent",
        AgentType.Fundamentals_Agent => "Fundamentals_Agent",
        AgentType.Technicals_Agent => "Technicals_Agent",
        AgentType.Forecaster_Agent => "Forecaster_Agent",
        AgentType.Report_Agent => "Report_Agent",
        AgentType.Summarizer_Agent => "Summarizer_Agent",
        AgentType.Ticker_Extraction_Agent => "Ticker_Extraction_Agent",
        _ => "Generic_Agent"
    };

    public async Task<PlanWithSteps?> GetPlanWithStepsAsync(string planId, string sessionId, CancellationToken ct = default)
    {
        var plan = await _store.GetPlanAsync(planId, sessionId, ct);
        if (plan is null) return null;
        var steps = await _store.GetStepsByPlanAsync(planId, sessionId, ct);
        return new PlanWithSteps
        {
            Id = plan.Id,
            SessionId = plan.SessionId,
            UserId = plan.UserId,
            InitialGoal = plan.InitialGoal,
            Summary = plan.Summary,
            OverallStatus = plan.OverallStatus,
            HumanClarificationRequest = plan.HumanClarificationRequest,
            HumanClarificationResponse = plan.HumanClarificationResponse,
            TotalSteps = plan.TotalSteps,
            CompletedSteps = plan.CompletedSteps,
            FailedSteps = plan.FailedSteps,
            Timestamp = plan.Timestamp,
            Ticker = plan.Ticker,
            Scope = plan.Scope,
            Steps = steps.ToList(),
            StepsRequiringApproval = steps.Count,
            Completed = steps.Count(s => s.Status == StepStatus.Completed)
        };
    }

    public async Task<ActionResponse> HandleStepApprovalAsync(HumanFeedback feedback, CancellationToken ct = default)
    {
        if (feedback.StepId is null) throw new ArgumentException("step_id required", nameof(feedback));
        var step = await _store.GetStepAsync(feedback.StepId, feedback.SessionId, ct);
        if (step is null) throw new InvalidOperationException($"Step {feedback.StepId} not found");

        if (!string.IsNullOrWhiteSpace(feedback.UpdatedAction))
        {
            step.Action = feedback.UpdatedAction;
        }

        if (!string.IsNullOrWhiteSpace(feedback.HumanFeedbackText))
        {
            step.HumanFeedback = feedback.HumanFeedbackText;
        }

        if (!feedback.Approved)
        {
            step.Status = StepStatus.Rejected;
            step.AgentReply = feedback.HumanFeedbackText ?? "Rejected by user";
            await _store.AddStepAsync(step, ct);

            await RecalculatePlanStatusAsync(step.PlanId, step.SessionId, ct);

            return new ActionResponse
            {
                StepId = step.Id,
                PlanId = step.PlanId,
                SessionId = step.SessionId,
                Success = false,
                Result = step.AgentReply,
                Error = feedback.HumanFeedbackText,
                Metadata = null
            };
        }

        step.Status = StepStatus.Executing;
        await _store.AddStepAsync(step, ct);

        var execResult = await ExecuteStepAsync(step, ct);
        step.Status = execResult.Success ? StepStatus.Completed : StepStatus.Failed;
        step.AgentReply = execResult.Message;
        step.ErrorMessage = execResult.Error;
        await _store.AddStepAsync(step, ct);

        await RecalculatePlanStatusAsync(step.PlanId, step.SessionId, ct);

        return new ActionResponse
        {
            StepId = step.Id,
            PlanId = step.PlanId,
            SessionId = step.SessionId,
            Success = execResult.Success,
            Result = execResult.Message,
            Error = execResult.Error,
            Metadata = null
        };
    }

    public Task<IReadOnlyList<Step>> GetStepsAsync(string planId, string sessionId, CancellationToken ct = default)
        => _store.GetStepsByPlanAsync(planId, sessionId, ct);

    public Task<IReadOnlyList<AgentMessage>> GetMessagesAsync(string planId, CancellationToken ct = default)
        => _store.GetMessagesByPlanAsync(planId, ct);

    public Task<IReadOnlyList<AgentMessage>> GetMessagesBySessionAsync(string sessionId, CancellationToken ct = default)
        => _store.GetMessagesBySessionAsync(sessionId, ct);

    public Task<IReadOnlyList<TaskListItem>> ListTasksAsync(string userId, int limit = 50, CancellationToken ct = default)
        => ListTasksInternalAsync(userId, limit, ct);

    private async Task<IReadOnlyList<TaskListItem>> ListTasksInternalAsync(string userId, int limit, CancellationToken ct)
    {
        var sessions = await _store.GetSessionsByUserAsync(userId, limit, ct);
        var items = new List<TaskListItem>();

        foreach (var session in sessions)
        {
            var plans = await _store.GetPlansBySessionAsync(session.SessionId, ct);
            foreach (var plan in plans)
            {
                var steps = await _store.GetStepsByPlanAsync(plan.Id, session.SessionId, ct);
                items.Add(new TaskListItem
                {
                    Id = plan.Id,
                    SessionId = plan.SessionId,
                    InitialGoal = plan.InitialGoal,
                    OverallStatus = plan.OverallStatus,
                    TotalSteps = plan.TotalSteps,
                    CompletedSteps = steps.Count(s => s.Status == StepStatus.Completed),
                    Timestamp = plan.Timestamp,
                    Ticker = plan.Ticker
                });
            }
        }

        return items.OrderByDescending(i => i.Timestamp).Take(limit).ToList();
    }

    public async Task<IReadOnlyList<Dictionary<string, object>>> GetHistoryAsync(string userId, int limit = 20, CancellationToken ct = default)
    {
        var tasks = await ListTasksInternalAsync(userId, limit, ct);
        var history = tasks.Select(t => new Dictionary<string, object>
        {
            ["session_id"] = t.SessionId,
            ["plan_id"] = t.Id,
            ["objective"] = t.InitialGoal,
            ["status"] = t.OverallStatus.ToString(),
            ["created_at"] = t.Timestamp,
            ["steps_count"] = t.TotalSteps
        }).ToList();
        return history;
    }

    public async Task<IReadOnlyList<TaskListItem>> GetPlansForSessionAsync(string sessionId, string userId, CancellationToken ct = default)
    {
        var plans = await _store.GetPlansBySessionAsync(sessionId, ct);
        return plans
            .Where(p => p.UserId == userId)
            .Select(p => new TaskListItem
            {
                Id = p.Id,
                SessionId = p.SessionId,
                InitialGoal = p.InitialGoal,
                OverallStatus = p.OverallStatus,
                TotalSteps = p.TotalSteps,
                CompletedSteps = p.CompletedSteps,
                Timestamp = p.Timestamp,
                Ticker = p.Ticker
            })
            .OrderByDescending(t => t.Timestamp)
            .ToList();
    }

    public Task DeleteSessionAsync(string sessionId, CancellationToken ct = default)
        => _store.DeleteSessionAsync(sessionId, ct);

    public async Task<Plan?> FindPlanAsync(string planId, CancellationToken ct = default)
    {
        var plans = await _store.GetAllPlansAsync(200, ct);
        return plans.FirstOrDefault(p => p.Id == planId);
    }

    public async Task<ActionResponse> InjectTaskAsync(string sessionId, string planId, string taskRequest, string objective, string userId, IEnumerable<Step>? currentSteps, CancellationToken ct = default)
    {
        var steps = (currentSteps ?? Enumerable.Empty<Step>()).ToList();
        if (!steps.Any())
        {
            steps = (await _store.GetStepsByPlanAsync(planId, sessionId, ct)).ToList();
        }

        var insertOrder = steps.Count + 1;
        var step = new Step
        {
            PlanId = planId,
            SessionId = sessionId,
            UserId = userId,
            Action = taskRequest,
            Agent = AgentType.Generic_Agent,
            Status = StepStatus.Planned,
            Order = insertOrder,
            HumanFeedback = objective
        };

        await _store.AddStepAsync(step, ct);

        var plan = await _store.GetPlanAsync(planId, sessionId, ct);
        if (plan is not null)
        {
            plan.TotalSteps += 1;
            await _store.UpdatePlanAsync(plan, ct);
        }

        return new ActionResponse
        {
            StepId = step.Id,
            PlanId = planId,
            SessionId = sessionId,
            Success = true,
            Result = "Task injected (stub)",
            Error = null,
            Metadata = new Dictionary<string, object>
            {
                ["inserted_at"] = insertOrder
            }
        };
    }

    public async Task<Plan?> RecalculatePlanStatusAsync(string planId, string sessionId, CancellationToken ct = default)
    {
        var plan = await _store.GetPlanAsync(planId, sessionId, ct);
        if (plan is null) return null;

        var steps = await _store.GetStepsByPlanAsync(planId, sessionId, ct);
        if (steps.All(s => s.Status == StepStatus.Completed))
        {
            plan.OverallStatus = PlanStatus.Completed;
        }
        else if (steps.Any(s => s.Status == StepStatus.Failed || s.Status == StepStatus.Rejected))
        {
            plan.OverallStatus = PlanStatus.Failed;
        }
        else
        {
            plan.OverallStatus = PlanStatus.In_Progress;
        }

        plan.CompletedSteps = steps.Count(s => s.Status == StepStatus.Completed);
        plan.FailedSteps = steps.Count(s => s.Status == StepStatus.Failed || s.Status == StepStatus.Rejected);
        plan.TotalSteps = steps.Count;

        await _store.UpdatePlanAsync(plan, ct);
        return plan;
    }

    private sealed record ExecutionResult(bool Success, string Message, string? Error);

    private async Task<string> BuildStepPromptAsync(Step step, Plan? plan, CancellationToken ct)
    {
        var goal = plan?.InitialGoal ?? step.HumanFeedback ?? step.Action;
        var contextBlock = await BuildContextBlockAsync(step, ct).ConfigureAwait(false);
        var toolList = step.Tools is { Count: > 0 } ? string.Join(", ", step.Tools) : "none";

        var sb = new StringBuilder();
        sb.AppendLine($"Objective: {goal}");
        if (!string.IsNullOrWhiteSpace(plan?.Ticker)) sb.AppendLine($"Ticker: {plan!.Ticker}");
        if (plan?.Scope is not null && plan.Scope.Any()) sb.AppendLine($"Scope: {string.Join(", ", plan.Scope)}");
        sb.AppendLine($"Step {step.Order ?? 0}: {step.Action}");
        sb.AppendLine($"Agent: {AgentTypeToName(step.Agent)}");
        sb.AppendLine($"Tool(s): {toolList}");
        sb.AppendLine($"Parameters: {FormatParameters(step)}");
        sb.AppendLine();
        sb.AppendLine("Previous findings (use as context, do not repeat verbatim):");
        sb.AppendLine(contextBlock);
        sb.AppendLine();
        sb.AppendLine("Provide concise findings (1-3 paragraphs). Cite key evidence. If data is missing, state what is missing and suggest next action.");
        return sb.ToString();
    }

    private async Task<string> BuildContextBlockAsync(Step step, CancellationToken ct)
    {
        var steps = await _store.GetStepsByPlanAsync(step.PlanId, step.SessionId, ct).ConfigureAwait(false);
        var completed = steps
            .Where(s => s.Id != step.Id && s.Order.HasValue && step.Order.HasValue && s.Order < step.Order &&
                        (s.Status == StepStatus.Completed || s.Status == StepStatus.Failed || s.Status == StepStatus.Rejected))
            .OrderBy(s => s.Order)
            .TakeLast(6)
            .ToList();

        if (!completed.Any())
        {
            return "(no prior steps completed)";
        }

        var contextLines = new List<string>();
        foreach (var prior in completed)
        {
            var summary = prior.AgentReply ?? prior.ErrorMessage ?? prior.HumanFeedback ?? "(no output recorded)";
            contextLines.Add($"- Step {prior.Order}: {prior.Action} [{AgentTypeToName(prior.Agent)}] => {TrimText(summary)}");
        }

        return string.Join('\n', contextLines);
    }

    private static string FormatParameters(Step step)
    {
        var parts = new List<string>();
        if (!string.IsNullOrWhiteSpace(step.HumanFeedback)) parts.Add($"objective_context={TrimText(step.HumanFeedback, 120)}");
        if (step.Tools is { Count: > 0 }) parts.Add($"tools=[{string.Join(",", step.Tools)}]");
        return parts.Count == 0 ? "none" : string.Join("; ", parts);
    }

    private static string TrimText(string? text, int max = 600)
    {
        if (string.IsNullOrEmpty(text)) return string.Empty;
        return text.Length <= max ? text : text[..max] + "...";
    }
}

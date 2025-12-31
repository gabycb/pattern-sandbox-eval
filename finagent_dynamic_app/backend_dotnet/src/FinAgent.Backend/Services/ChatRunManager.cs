using FinAgent.Backend.Models;

namespace FinAgent.Backend.Services;

public class ChatRunManager
{
    private readonly TaskOrchestrator _orchestrator;
    private readonly ChatPubSubPublisher _publisher;
    private readonly Dictionary<string, Task> _tasks = new();
    private readonly Dictionary<string, CancellationTokenSource> _cancels = new();

    public ChatRunManager(TaskOrchestrator orchestrator, ChatPubSubPublisher publisher)
    {
        _orchestrator = orchestrator;
        _publisher = publisher;
    }

    public bool IsRunning(string taskId) => _tasks.TryGetValue(taskId, out var t) && !t.IsCompleted;

    public Task<StartChatResponse> StartChatAsync(StartChatRequest request, CancellationToken ct = default)
    {
        var taskId = request.TaskId;
        if (IsRunning(taskId))
        {
            return Task.FromResult(new StartChatResponse
            {
                TaskId = taskId,
                SessionId = request.SessionId,
                Status = "already_running"
            });
        }

        var cts = CancellationTokenSource.CreateLinkedTokenSource(ct);
        _cancels[taskId] = cts;
        _tasks[taskId] = Task.Run(async () => await ExecuteAsync(taskId, request.SessionId, cts.Token), cts.Token);

        return Task.FromResult(new StartChatResponse
        {
            TaskId = taskId,
            SessionId = request.SessionId,
            Status = "started"
        });
    }

    public Task StartRunAsync(string taskId, string sessionId, string userId, CancellationToken ct = default)
        => StartChatAsync(new StartChatRequest { TaskId = taskId, SessionId = sessionId }, ct);

    public Task<bool> StopChatAsync(string taskId, CancellationToken ct = default)
    {
        if (_cancels.TryGetValue(taskId, out var cts))
        {
            cts.Cancel();
            return Task.FromResult(true);
        }
        return Task.FromResult(false);
    }

    public Task<bool> CancelRunAsync(string taskId, CancellationToken ct = default) => StopChatAsync(taskId, ct);

    private async Task ExecuteAsync(string taskId, string sessionId, CancellationToken ct)
    {
        var snapshot = await _orchestrator.GetPlanWithStepsAsync(taskId, sessionId, ct);
        if (snapshot is null) return;

        foreach (var step in snapshot.Steps.OrderBy(s => s.Order))
        {
            if (ct.IsCancellationRequested) return;
            if (step.Status == StepStatus.Completed || step.Status == StepStatus.Rejected) continue;

            await _publisher.SendEventAsync(new ChatEventPayload
            {
                Type = "step_started",
                TaskId = taskId,
                SessionId = sessionId,
                Data = new Dictionary<string, object> { ["step"] = step }
            }, ct);

            var feedback = new HumanFeedback
            {
                StepId = step.Id,
                PlanId = taskId,
                SessionId = sessionId,
                Approved = true
            };
            var result = await _orchestrator.HandleStepApprovalAsync(feedback, ct);

            await _publisher.SendEventAsync(new ChatEventPayload
            {
                Type = result.Success ? "step_completed" : "step_failed",
                TaskId = taskId,
                SessionId = sessionId,
                Data = new Dictionary<string, object> { ["step"] = step, ["success"] = result.Success }
            }, ct);

            if (!result.Success)
            {
                break;
            }
        }

        await _orchestrator.RecalculatePlanStatusAsync(taskId, sessionId, ct);

        await _publisher.SendEventAsync(new ChatEventPayload
        {
            Type = "run_finished",
            TaskId = taskId,
            SessionId = sessionId,
            Data = new Dictionary<string, object>()
        }, ct);
    }
}

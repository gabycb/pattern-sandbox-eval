using FinAgent.Backend.Infrastructure;
using FinAgent.Backend.Models;
using FinAgent.Backend.Services;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Options;

namespace FinAgent.Backend.Controllers;

[ApiController]
[Route("api/chat")]
public class ChatController : ControllerBase
{
    private readonly ChatRunManager _chatRunManager;
    private readonly TaskOrchestrator _orchestrator;
    private readonly ChatPubSubPublisher _publisher;
    private readonly AppSettings _settings;

    public ChatController(ChatRunManager chatRunManager, TaskOrchestrator orchestrator, ChatPubSubPublisher publisher, IOptions<AppSettings> settings)
    {
        _chatRunManager = chatRunManager;
        _orchestrator = orchestrator;
        _publisher = publisher;
        _settings = settings.Value;
    }

    [HttpGet("config")]
    [ProducesResponseType(typeof(ChatConfigResponse), StatusCodes.Status200OK)]
    public IActionResult GetConfig()
    {
        return Ok(new ChatConfigResponse { Enabled = _settings.EnableChatAutorun });
    }

    [HttpPost("objective")]
    [ProducesResponseType(typeof(ChatObjectiveResponse), StatusCodes.Status200OK)]
    public async Task<IActionResult> CreateChatPlan([FromBody] ChatObjectiveRequest request, CancellationToken ct)
    {
        if (!_settings.EnableChatAutorun) return NotFound(new { detail = "Chat autorun is disabled" });

        var userId = HttpContext.Request.Headers["x-ms-client-principal-id"].FirstOrDefault();
        if (string.IsNullOrWhiteSpace(userId)) return Unauthorized(new { detail = "User authentication required" });

        var input = new InputTask
        {
            Description = request.Objective,
            UserId = userId,
            Ticker = request.Ticker,
            Scope = request.Scope,
            SessionId = request.SessionId
        };

        var planWithSteps = await _orchestrator.CreatePlanFromObjectiveAsync(input, userId, ct);
        var access = await _publisher.GetClientAccessAsync(userId, planWithSteps.Id, ct);

        return Ok(new ChatObjectiveResponse
        {
            TaskId = planWithSteps.Id,
            SessionId = planWithSteps.SessionId,
            Plan = planWithSteps,
            WebPubSubUrl = access != null && access.ContainsKey("url") ? access["url"] : null,
            WebPubSubGroup = access != null && access.ContainsKey("group") ? access["group"] : null
        });
    }

    [HttpPost("confirm")]
    [ProducesResponseType(typeof(ChatConfirmResponse), StatusCodes.Status200OK)]
    public async Task<IActionResult> ConfirmChatPlan([FromBody] ChatConfirmRequest payload, CancellationToken ct)
    {
        if (!_settings.EnableChatAutorun) return NotFound(new { detail = "Chat autorun is disabled" });

        var plan = await _orchestrator.GetPlanWithStepsAsync(payload.TaskId, payload.SessionId ?? string.Empty, ct);
        if (plan is null)
        {
            var found = await _orchestrator.FindPlanAsync(payload.TaskId, ct);
            if (found is not null)
            {
                plan = await _orchestrator.GetPlanWithStepsAsync(found.Id, found.SessionId, ct);
            }
        }

        if (plan is null) return NotFound(new { detail = "Plan not found" });

        var sessionId = plan.SessionId;

        if (payload.Steps is not null)
        {
            foreach (var patch in payload.Steps)
            {
                var step = await _orchestrator.Store.GetStepAsync(patch.Id, sessionId, ct);
                if (step is null) continue;
                if (!string.IsNullOrWhiteSpace(patch.Action)) step.Action = patch.Action;
                if (!string.IsNullOrWhiteSpace(patch.HumanFeedback)) step.HumanFeedback = patch.HumanFeedback;
                await _orchestrator.Store.AddStepAsync(step, ct);
            }
        }

        var refreshedPlan = await _orchestrator.GetPlanWithStepsAsync(plan.Id, sessionId, ct) ?? plan;
        if (payload.Action == "modify")
        {
            return Ok(new ChatConfirmResponse { TaskId = refreshedPlan.Id, SessionId = sessionId, Plan = refreshedPlan });
        }

        if (_settings.EnableChatAutorun)
        {
            await _chatRunManager.StartRunAsync(refreshedPlan.Id, sessionId, plan.UserId, ct);
        }

        return Ok(new ChatConfirmResponse { TaskId = refreshedPlan.Id, SessionId = sessionId, Plan = refreshedPlan });
    }

    [HttpPost("cancel")]
    public async Task<IActionResult> CancelChat([FromBody] ChatCancelRequest payload, CancellationToken ct)
    {
        if (!_settings.EnableChatAutorun) return NotFound(new { detail = "Chat autorun is disabled" });

        var plan = await _orchestrator.FindPlanAsync(payload.TaskId, ct);
        if (plan is null) return NotFound(new { detail = "Plan not found" });

        var stopped = await _chatRunManager.CancelRunAsync(payload.TaskId, ct);
        if (stopped)
        {
            plan.OverallStatus = PlanStatus.Cancelled;
            await _orchestrator.Store.UpdatePlanAsync(plan, ct);
            return Ok(new { message = "Cancellation requested" });
        }

        plan.OverallStatus = PlanStatus.Cancelled;
        await _orchestrator.Store.UpdatePlanAsync(plan, ct);
        return Ok(new { message = "No active run to cancel, plan marked cancelled" });
    }

    [HttpGet("status")]
    [ProducesResponseType(typeof(ChatStatusResponse), StatusCodes.Status200OK)]
    public async Task<IActionResult> GetStatus([FromQuery] string taskId, [FromQuery] string? sessionId, CancellationToken ct)
    {
        if (!_settings.EnableChatAutorun) return NotFound(new { detail = "Chat autorun is disabled" });

        var resolvedSession = sessionId;
        if (string.IsNullOrWhiteSpace(resolvedSession))
        {
            var plan = await _orchestrator.FindPlanAsync(taskId, ct);
            if (plan is null) return NotFound(new { detail = $"Plan {taskId} not found" });
            resolvedSession = plan.SessionId;
        }

        var planWithSteps = await _orchestrator.GetPlanWithStepsAsync(taskId, resolvedSession!, ct);
        if (planWithSteps is null) return NotFound(new { detail = $"Plan {taskId} not found" });

        var messages = await _orchestrator.GetMessagesAsync(taskId, ct);

        return Ok(new ChatStatusResponse
        {
            TaskId = planWithSteps.Id,
            SessionId = planWithSteps.SessionId,
            Plan = planWithSteps,
            Messages = messages
        });
    }

    [HttpPost("start")]
    [ProducesResponseType(typeof(StartChatResponse), StatusCodes.Status200OK)]
    public async Task<IActionResult> StartChat([FromBody] StartChatRequest request, CancellationToken ct)
    {
        var response = await _chatRunManager.StartChatAsync(request, ct);
        return Ok(response);
    }

    [HttpPost("stop")]
    [ProducesResponseType(StatusCodes.Status200OK)]
    public async Task<IActionResult> StopChat([FromBody] StopChatRequest request, CancellationToken ct)
    {
        var stopped = await _chatRunManager.StopChatAsync(request.TaskId, ct);
        return Ok(new { message = stopped ? "Stopped" : "Not running" });
    }
}

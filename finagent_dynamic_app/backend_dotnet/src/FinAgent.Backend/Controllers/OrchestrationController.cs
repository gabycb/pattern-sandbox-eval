using FinAgent.Backend.Models;
using FinAgent.Backend.Services;
using Microsoft.AspNetCore.Mvc;

namespace FinAgent.Backend.Controllers;

[ApiController]
[Route("api")]
public class OrchestrationController : ControllerBase
{
    private readonly TaskOrchestrator _orchestrator;

    public OrchestrationController(TaskOrchestrator orchestrator)
    {
        _orchestrator = orchestrator;
    }

    [HttpGet("tasks")]
    [ProducesResponseType(typeof(IEnumerable<TaskListItem>), StatusCodes.Status200OK)]
    public async Task<IActionResult> ListTasks([FromQuery] int limit = 50, CancellationToken ct = default)
    {
        var userId = HttpContext.Request.Headers["x-ms-client-principal-id"].FirstOrDefault();
        if (string.IsNullOrWhiteSpace(userId)) return Unauthorized(new { detail = "User authentication required" });
        var tasks = await _orchestrator.ListTasksAsync(userId, limit, ct);
        return Ok(tasks);
    }

    [HttpGet("history")]
    [ProducesResponseType(typeof(IEnumerable<Dictionary<string, object>>), StatusCodes.Status200OK)]
    public async Task<IActionResult> GetHistory([FromQuery] int limit = 20, CancellationToken ct = default)
    {
        var userId = HttpContext.Request.Headers["x-ms-client-principal-id"].FirstOrDefault();
        if (string.IsNullOrWhiteSpace(userId)) return Unauthorized(new { detail = "User authentication required" });
        var history = await _orchestrator.GetHistoryAsync(userId, limit, ct);
        return Ok(history);
    }

    [HttpPost("input_task")]
    [ProducesResponseType(typeof(PlanWithSteps), StatusCodes.Status200OK)]
    public async Task<IActionResult> CreatePlan([FromBody] InputTask inputTask, CancellationToken ct)
    {
        var userId = HttpContext.Request.Headers["x-ms-client-principal-id"].FirstOrDefault() ?? "local-user";
        var plan = await _orchestrator.CreatePlanFromObjectiveAsync(inputTask, userId, ct);
        return Ok(plan);
    }

    [HttpGet("plans/{sessionId}/{planId}")]
    [ProducesResponseType(typeof(PlanWithSteps), StatusCodes.Status200OK)]
    public async Task<IActionResult> GetPlan(string sessionId, string planId, CancellationToken ct)
    {
        var plan = await _orchestrator.GetPlanWithStepsAsync(planId, sessionId, ct);
        if (plan is null) return NotFound(new { detail = $"Plan {planId} not found" });
        return Ok(plan);
    }

    [HttpGet("plans/{sessionId}")]
    [ProducesResponseType(typeof(IEnumerable<TaskListItem>), StatusCodes.Status200OK)]
    public async Task<IActionResult> ListPlansForSession(string sessionId, [FromQuery] string user_id, CancellationToken ct)
    {
        var plans = await _orchestrator.GetPlansForSessionAsync(sessionId, user_id, ct);
        return Ok(plans);
    }

    [HttpGet("steps/{sessionId}/{planId}")]
    [ProducesResponseType(typeof(IEnumerable<Step>), StatusCodes.Status200OK)]
    public async Task<IActionResult> GetSteps(string sessionId, string planId, CancellationToken ct)
    {
        var steps = await _orchestrator.GetStepsAsync(planId, sessionId, ct);
        return Ok(steps);
    }

    [HttpGet("messages/{sessionId}")]
    [ProducesResponseType(typeof(IEnumerable<AgentMessage>), StatusCodes.Status200OK)]
    public async Task<IActionResult> GetMessages(string sessionId, [FromQuery] string? plan_id, CancellationToken ct)
    {
        var planId = plan_id ?? string.Empty;
        if (string.IsNullOrWhiteSpace(planId))
        {
            var sessionMessages = await _orchestrator.GetMessagesBySessionAsync(sessionId, ct);
            return Ok(sessionMessages);
        }
        var messages = await _orchestrator.GetMessagesAsync(planId, ct);
        return Ok(messages);
    }

    [HttpPost("inject_task")]
    public async Task<IActionResult> InjectTask([FromBody] Dictionary<string, object> payload, CancellationToken ct)
    {
        var sessionId = payload.TryGetValue("session_id", out var s) ? s?.ToString() : null;
        var planId = payload.TryGetValue("plan_id", out var p) ? p?.ToString() : null;
        var taskRequest = payload.TryGetValue("task_request", out var t) ? t?.ToString() : null;
        var objective = payload.TryGetValue("objective", out var o) ? o?.ToString() : null;
        var currentSteps = payload.TryGetValue("current_steps", out var c) && c is IEnumerable<Step> steps ? steps : null;
        var userId = HttpContext.Request.Headers["x-ms-client-principal-id"].FirstOrDefault();

        if (string.IsNullOrWhiteSpace(sessionId) || string.IsNullOrWhiteSpace(planId) || string.IsNullOrWhiteSpace(taskRequest) || string.IsNullOrWhiteSpace(objective))
        {
            return BadRequest(new { detail = "Missing required fields: session_id, plan_id, task_request, objective" });
        }

        if (string.IsNullOrWhiteSpace(userId)) return Unauthorized(new { detail = "User authentication required" });

        var result = await _orchestrator.InjectTaskAsync(sessionId, planId, taskRequest, objective, userId, currentSteps, ct);
        var insertedAt = result.Metadata != null && result.Metadata.TryGetValue("inserted_at", out var val)
            ? val
            : null;
        return Ok(new Dictionary<string, object?>
        {
            ["success"] = true,
            ["action"] = "added",
            ["new_step_id"] = result.StepId,
            ["inserted_at"] = insertedAt
        });
    }

    [HttpPost("approve_step")]
    [ProducesResponseType(typeof(ActionResponse), StatusCodes.Status200OK)]
    public async Task<IActionResult> ApproveStep([FromBody] HumanFeedback feedback, CancellationToken ct)
    {
        var result = await _orchestrator.HandleStepApprovalAsync(feedback, ct);
        return Ok(result);
    }

    [HttpPost("approve_steps")]
    [ProducesResponseType(typeof(IEnumerable<ActionResponse>), StatusCodes.Status200OK)]
    public async Task<IActionResult> ApproveSteps([FromBody] IEnumerable<HumanFeedback> feedbacks, CancellationToken ct)
    {
        var results = new List<ActionResponse>();
        foreach (var fb in feedbacks)
        {
            results.Add(await _orchestrator.HandleStepApprovalAsync(fb, ct));
        }
        return Ok(results);
    }

    [HttpDelete("sessions/{sessionId}")]
    public async Task<IActionResult> DeleteSession(string sessionId, CancellationToken ct)
    {
        await _orchestrator.DeleteSessionAsync(sessionId, ct);
        return Ok(new { message = $"Session {sessionId} deleted" });
    }

    [HttpPost("recalculate_plan_status/{sessionId}/{planId}")]
    public async Task<IActionResult> RecalculatePlanStatus(string sessionId, string planId, CancellationToken ct)
    {
        var plan = await _orchestrator.RecalculatePlanStatusAsync(planId, sessionId, ct);
        if (plan is null) return NotFound(new { detail = "Plan not found" });
        return Ok(new
        {
            success = true,
            plan_id = planId,
            session_id = sessionId,
            overall_status = plan.OverallStatus
        });
    }
}

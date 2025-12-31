using System.Collections.Concurrent;
using FinAgent.Backend.Models;

namespace FinAgent.Backend.Services;

/// <summary>
/// Minimal in-memory store to allow local runs/tests without Cosmos.
/// </summary>
public class InMemoryStore : ICosmosMemoryStore
{
    private readonly ConcurrentDictionary<string, Session> _sessions = new();
    private readonly ConcurrentDictionary<(string planId, string sessionId), Plan> _plans = new();
    private readonly ConcurrentDictionary<(string planId, string sessionId), List<Step>> _steps = new();
    private readonly ConcurrentDictionary<string, List<AgentMessage>> _messagesByPlan = new();
    private readonly ConcurrentDictionary<string, List<AgentMessage>> _messagesBySession = new();

    public Task CreateSessionAsync(Session session, CancellationToken ct = default)
    {
        _sessions[session.SessionId] = session;
        return Task.CompletedTask;
    }

    public Task AddPlanAsync(Plan plan, CancellationToken ct = default)
    {
        _plans[(plan.Id, plan.SessionId)] = plan;
        return Task.CompletedTask;
    }

    public Task<Plan?> GetPlanAsync(string planId, string sessionId, CancellationToken ct = default)
    {
        _plans.TryGetValue((planId, sessionId), out var plan);
        return Task.FromResult(plan);
    }

    public Task UpdatePlanAsync(Plan plan, CancellationToken ct = default)
    {
        _plans[(plan.Id, plan.SessionId)] = plan;
        return Task.CompletedTask;
    }

    public Task AddStepAsync(Step step, CancellationToken ct = default)
    {
        var key = (step.PlanId, step.SessionId);
        var list = _steps.GetOrAdd(key, _ => new List<Step>());
        var existing = list.FindIndex(s => s.Id == step.Id);
        if (existing >= 0) list[existing] = step; else list.Add(step);
        return Task.CompletedTask;
    }

    public Task<Step?> GetStepAsync(string stepId, string sessionId, CancellationToken ct = default)
    {
        var match = _steps.Values.SelectMany(s => s).FirstOrDefault(s => s.Id == stepId && s.SessionId == sessionId);
        return Task.FromResult(match);
    }

    public Task<IReadOnlyList<Step>> GetStepsByPlanAsync(string planId, string sessionId, CancellationToken ct = default)
    {
        var key = (planId, sessionId);
        if (_steps.TryGetValue(key, out var list))
        {
            return Task.FromResult((IReadOnlyList<Step>)list.OrderBy(s => s.Order).ToList());
        }
        return Task.FromResult((IReadOnlyList<Step>)Array.Empty<Step>());
    }

    public Task AddMessageAsync(AgentMessage message, CancellationToken ct = default)
    {
        var list = _messagesByPlan.GetOrAdd(message.PlanId, _ => new List<AgentMessage>());
        list.Add(message);
        var sessionList = _messagesBySession.GetOrAdd(message.SessionId, _ => new List<AgentMessage>());
        sessionList.Add(message);
        return Task.CompletedTask;
    }

    public Task<IReadOnlyList<AgentMessage>> GetMessagesByPlanAsync(string planId, CancellationToken ct = default)
    {
        if (_messagesByPlan.TryGetValue(planId, out var list))
        {
            return Task.FromResult((IReadOnlyList<AgentMessage>)list.OrderBy(m => m.Timestamp).ToList());
        }
        return Task.FromResult((IReadOnlyList<AgentMessage>)Array.Empty<AgentMessage>());
    }

    public Task<IReadOnlyList<AgentMessage>> GetMessagesBySessionAsync(string sessionId, CancellationToken ct = default)
    {
        if (_messagesBySession.TryGetValue(sessionId, out var list))
        {
            return Task.FromResult((IReadOnlyList<AgentMessage>)list.OrderBy(m => m.Timestamp).ToList());
        }
        return Task.FromResult((IReadOnlyList<AgentMessage>)Array.Empty<AgentMessage>());
    }

    public Task<IReadOnlyList<Session>> GetSessionsByUserAsync(string userId, int limit = 50, CancellationToken ct = default)
    {
        var items = _sessions.Values
            .Where(s => s.UserId == userId)
            .OrderByDescending(s => s.CreatedAt)
            .Take(limit)
            .ToList();
        return Task.FromResult((IReadOnlyList<Session>)items);
    }

    public Task<IReadOnlyList<Plan>> GetPlansBySessionAsync(string sessionId, CancellationToken ct = default)
    {
        var items = _plans.Where(kvp => kvp.Key.sessionId == sessionId)
            .Select(kvp => kvp.Value)
            .OrderByDescending(p => p.Timestamp)
            .ToList();
        return Task.FromResult((IReadOnlyList<Plan>)items);
    }

    public Task<IReadOnlyList<Plan>> GetAllPlansAsync(int limit = 50, CancellationToken ct = default)
    {
        var items = _plans.Values
            .OrderByDescending(p => p.Timestamp)
            .Take(limit)
            .ToList();
        return Task.FromResult((IReadOnlyList<Plan>)items);
    }

    public Task DeleteSessionAsync(string sessionId, CancellationToken ct = default)
    {
        _sessions.TryRemove(sessionId, out _);
        foreach (var key in _plans.Keys.Where(k => k.sessionId == sessionId).ToList())
        {
            _plans.TryRemove(key, out _);
            _steps.TryRemove(key, out _);
            _messagesByPlan.TryRemove(key.planId, out _);
            _messagesBySession.TryRemove(sessionId, out _);
        }
        return Task.CompletedTask;
    }
}

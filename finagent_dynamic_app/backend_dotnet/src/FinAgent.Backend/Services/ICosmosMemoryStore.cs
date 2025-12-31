using FinAgent.Backend.Models;

namespace FinAgent.Backend.Services;

public interface ICosmosMemoryStore
{
    Task CreateSessionAsync(Session session, CancellationToken ct = default);
    Task<Plan?> GetPlanAsync(string planId, string sessionId, CancellationToken ct = default);
    Task AddPlanAsync(Plan plan, CancellationToken ct = default);
    Task UpdatePlanAsync(Plan plan, CancellationToken ct = default);
    Task AddStepAsync(Step step, CancellationToken ct = default);
    Task<Step?> GetStepAsync(string stepId, string sessionId, CancellationToken ct = default);
    Task<IReadOnlyList<Step>> GetStepsByPlanAsync(string planId, string sessionId, CancellationToken ct = default);
    Task AddMessageAsync(AgentMessage message, CancellationToken ct = default);
    Task<IReadOnlyList<AgentMessage>> GetMessagesByPlanAsync(string planId, CancellationToken ct = default);
    Task<IReadOnlyList<AgentMessage>> GetMessagesBySessionAsync(string sessionId, CancellationToken ct = default);
    Task<IReadOnlyList<Session>> GetSessionsByUserAsync(string userId, int limit = 50, CancellationToken ct = default);
    Task<IReadOnlyList<Plan>> GetPlansBySessionAsync(string sessionId, CancellationToken ct = default);
    Task<IReadOnlyList<Plan>> GetAllPlansAsync(int limit = 50, CancellationToken ct = default);
    Task DeleteSessionAsync(string sessionId, CancellationToken ct = default);
}

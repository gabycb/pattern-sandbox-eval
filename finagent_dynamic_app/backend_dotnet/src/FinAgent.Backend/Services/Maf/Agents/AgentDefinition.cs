namespace FinAgent.Backend.Services.Maf.Agents;

public sealed record AgentDefinition(
    string TypeName,
    string SystemPrompt,
    string? Description = null,
    string? ModelDeployment = null,
    IReadOnlyList<string>? Capabilities = null);

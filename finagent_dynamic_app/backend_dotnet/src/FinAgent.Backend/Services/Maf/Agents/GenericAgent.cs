namespace FinAgent.Backend.Services.Maf.Agents;

internal static class GenericAgent
{
    public const string Name = "Generic_Agent";

    public static AgentDefinition Definition => new(
        TypeName: Name,
        SystemPrompt: "You are a helpful financial research assistant. Execute the task with clear, concise findings and cite evidence.",
        ModelDeployment: "chat41mini",
        Capabilities: new[] { "generic_research" });
}

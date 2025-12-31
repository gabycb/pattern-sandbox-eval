namespace FinAgent.Backend.Services.Maf.Agents;

internal static class PlannerAgent
{
    public const string Name = "Planner_Agent";

    public static AgentDefinition Definition => new(
        TypeName: Name,
        SystemPrompt: "You are the lead financial research planner. Analyse objectives, determine the required research tracks (company profile, SEC filings, earnings, fundamentals, technicals, forecasts, summaries, reports) and produce an execution plan tailored to the user's goals.",
        ModelDeployment: "chato1",
        Capabilities: new[] { "plan_research_tracks", "route_tasks", "select_tools" });
}

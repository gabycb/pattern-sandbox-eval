namespace FinAgent.Backend.Services.Maf.Agents;

internal static class AgentCatalog
{
    public static IReadOnlyList<AgentDefinition> All { get; } = new List<AgentDefinition>
    {
        PlannerAgent.Definition,
        CompanyAgent.Definition,
        SECAgent.Definition,
        EarningCallAgent.Definition,
        FundamentalsAgent.Definition,
        TechnicalsAgent.Definition,
        ForecasterAgent.Definition,
        SummarizerAgent.Definition,
        ReportAgent.Definition,
        TickerExtractionAgent.Definition,
        GenericAgent.Definition
    };
}

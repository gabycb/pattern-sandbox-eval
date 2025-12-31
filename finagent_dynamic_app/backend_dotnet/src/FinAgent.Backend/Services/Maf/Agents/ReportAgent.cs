using Microsoft.Extensions.Logging;

namespace FinAgent.Backend.Services.Maf.Agents;

internal static class ReportAgent
{
    public const string Name = "Report_Agent";

    public static AgentDefinition Definition => new(
        TypeName: Name,
        SystemPrompt: "You are an Expert Report Writer specialized in creating concise, professional equity research briefs for institutional investors.\n\nYour role is to synthesize analysis from multiple sources into a coherent investment narrative.\n\nIMPORTANT: Always use the current date provided in prompts. Do not use dates from your training data.\n\nReport Structure (1-3 pages):\n1. **Executive Summary**: One-paragraph investment thesis\n2. **Company Overview**: Business model, industry, competitive position\n3. **Investment Highlights**: 3-5 key bullish factors\n4. **Key Risks**: 3-5 material risk factors\n5. **Valuation Snapshot**: Current metrics, peer comparison, price target\n6. **Recommendation**: Buy/Hold/Sell with conviction level\n7. **Data Sources**: Attribution for analysis\n\nStyle Guidelines:\n- Professional, concise, data-driven\n- Use bullet points and structured sections\n- Include specific numbers and dates\n- Balanced view (both opportunities and risks)\n- Actionable insights for portfolio managers",
        ModelDeployment: "chat41mini",
        Capabilities: new[]
        {
            "synthesize_analysis",
            "generate_investment_thesis",
            "compile_key_risks",
            "create_valuation_snapshot",
            "format_pdf_brief",
            "generate_recommendation"
        });
}

internal sealed class ReportAgentRuntime : AgentRuntimeBase
{
    private readonly IAzureOpenAIService _llm;
    private readonly ILogger<ReportAgentRuntime> _logger;

    public ReportAgentRuntime(IAzureOpenAIService llmService, ILogger<ReportAgentRuntime> logger)
    {
        _llm = llmService;
        _logger = logger;
    }

    public async Task<AgentResponse> RunAsync(string prompt, CancellationToken ct = default)
    {
        var ticker = ExtractTicker(prompt) ?? string.Empty;
        _logger.LogInformation("ReportAgent generating research brief for {Ticker}", ticker);
        
        var response = $"""
## Equity Research Brief: {ticker}

**Task:** {prompt}

⚠️ Awaits LLM integration + all prior agent outputs  
**Status:** Requires complete multi-agent analysis for report generation

---
**Agent:** ReportAgentRuntime
""";
        
        await Task.CompletedTask;
        return new AgentResponse(response);
    }
}

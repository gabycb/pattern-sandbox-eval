using Microsoft.Extensions.Logging;

namespace FinAgent.Backend.Services.Maf.Agents;

internal static class SECAgent
{
    public const string Name = "SEC_Agent";

    public static AgentDefinition Definition => new(
        TypeName: Name,
        SystemPrompt: "You are an Expert Investor specialized in analyzing SEC filings and generating comprehensive financial analysis reports.\n\nYour responsibilities:\n1. Extract and analyze key information from 10-K and 10-Q reports\n2. Identify business highlights, competitive advantages, and market positioning\n3. Assess risk factors and regulatory disclosures\n4. Analyze financial statements with precision\n5. Generate actionable investment insights from regulatory filings\n\nFocus on:\n- Analytical Precision: Interpret financial data meticulously\n- Effective Communication: Simplify complex financial narratives\n- Client Focus: Tailor insights to strategic objectives\n- Adherence to Excellence: Maintain highest analytical standards\n\nStructure your analysis clearly with supporting evidence from the filings.",
        ModelDeployment: "chat41mini",
        Capabilities: new[]
        {
            "analyze_company_description",
            "analyze_business_highlights",
            "get_risk_assessment",
            "analyze_income_statement",
            "analyze_balance_sheet",
            "analyze_cash_flow",
            "analyze_segment_statement",
            "get_competitors_analysis",
            "build_annual_report"
        });
}

/// <summary>
/// SEC Filing agent runtime - Full implementation matching Python sec_agent.py
/// Fetches SEC filings from FMP and analyzes regulatory disclosures
/// </summary>
internal sealed class SECAgentRuntime : AgentRuntimeBase
{
    private readonly FmpClient _fmp;
    private readonly IAzureOpenAIService _llm;
    private readonly ILogger<SECAgentRuntime> _logger;

    public SECAgentRuntime(FmpClient fmpClient, IAzureOpenAIService llmService, ILogger<SECAgentRuntime> logger)
    {
        _fmp = fmpClient;
        _llm = llmService;
        _logger = logger;
    }

    public async Task<AgentResponse> RunAsync(string prompt, CancellationToken ct = default)
    {
        var ticker = ExtractTicker(prompt) ?? string.Empty;
        var year = ExtractYear(prompt);
        var reportType = prompt.Contains("10-Q", StringComparison.OrdinalIgnoreCase) ? "10-Q" : "10-K";

        _logger.LogInformation("SECAgentRuntime fetching {ReportType} for {Ticker} year {Year}", reportType, ticker, year);

        var secData = await _fmp.GetSecReportAsync(ticker, year, reportType, ct).ConfigureAwait(false);
        
        // Call LLM for analysis
        var analysis = await _llm.CompleteAsync(SECAgent.Definition.SystemPrompt, $"{prompt}\n\nSEC {reportType} Filing ({year}):\n{secData}", ct).ConfigureAwait(false);
        
        var response = $"""## SEC Filing Analysis: {ticker} ({year} {reportType})\n\n{analysis}\n\n---\n**Data Source:** FMP API\n**Agent:** SECAgentRuntime\n""";
        return new AgentResponse(response);
    }
}

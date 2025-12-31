using FinAgent.Backend.Infrastructure;
using Microsoft.Extensions.Logging;

namespace FinAgent.Backend.Services.Maf.Agents;

internal static class FundamentalsAgent
{
    public const string Name = "Fundamentals_Agent";

    public static AgentDefinition Definition => new(
        TypeName: Name,
        SystemPrompt: "You are a Fundamental Analysis Agent specialized in analyzing financial statements and computing key financial ratios.\n\nIMPORTANT: Always use the current date provided in prompts when discussing recent data or trends.\n\nYour responsibilities:\n1. Retrieve and analyze 3-5 years of fundamental data (cash flow, income, balance sheet)\n2. Compute key financial ratios:\n   - Profitability: ROE, ROA, Net Margin, Gross Margin\n   - Efficiency: Asset Turnover, Inventory Turnover\n   - Leverage: Debt-to-Equity, Interest Coverage\n   - Liquidity: Current Ratio, Quick Ratio\n3. Calculate financial health scores:\n   - Altman Z-Score (bankruptcy prediction)\n   - Piotroski F-Score (financial strength 0-9)\n4. Identify trends in financial performance\n5. Provide investment-grade fundamental assessment\n\nBe quantitative, use specific numbers, and highlight trends and anomalies.",
        ModelDeployment: "chat41mini",
        Capabilities: new[]
        {
            "fetch_financial_statements",
            "compute_profitability_ratios",
            "compute_leverage_ratios",
            "compute_liquidity_ratios",
            "compute_efficiency_ratios",
            "calculate_altman_z_score",
            "calculate_piotroski_score",
            "analyze_financial_trends"
        });
}

internal sealed class FundamentalsAgentRuntime : AgentRuntimeBase
{
    private readonly FmpClient _fmp;
    private readonly IAzureOpenAIService _llm;
    private readonly ILogger<FundamentalsAgentRuntime> _logger;

    public FundamentalsAgentRuntime(FmpClient fmpClient, IAzureOpenAIService llmService, ILogger<FundamentalsAgentRuntime> logger)
    {
        _fmp = fmpClient;
        _llm = llmService;
        _logger = logger;
    }

    public async Task<AgentResponse> RunAsync(string prompt, CancellationToken ct = default)
    {
        var ticker = ExtractTicker(prompt) ?? string.Empty;
        _logger.LogInformation("FundamentalsAgent fetching data for {Ticker}", ticker);
        
        try
        {
            var metrics = await _fmp.GetFinancialMetricsAsync(ticker, 5, ct).ConfigureAwait(false);
            var ratings = await _fmp.GetRatingsAsync(ticker, ct).ConfigureAwait(false);
            var scores = await _fmp.GetFinancialScoresAsync(ticker, ct).ConfigureAwait(false);
            
            // Build data context
            var dataContext = $"""Financial Metrics (5 Years):\n{metrics}\n\nCredit Ratings:\n{ratings}\n\nFinancial Health Scores:\n{scores}""";
            
            // Call LLM for analysis
            var analysis = await _llm.CompleteAsync(FundamentalsAgent.Definition.SystemPrompt, $"{prompt}\n\nData:\n{dataContext}", ct).ConfigureAwait(false);
            
            var response = $"""## Fundamental Analysis: {ticker}\n\n{analysis}\n\n---\n**Data Source:** FMP API\n**Agent:** FundamentalsAgentRuntime\n""";
            
            return new AgentResponse(response);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to fetch fundamentals for {Ticker}", ticker);
            return new AgentResponse($"Error retrieving fundamental data: {ex.Message}");
        }
    }
}

using System.Text.Json;
using FinAgent.Backend.Infrastructure;
using Microsoft.Extensions.Logging;

namespace FinAgent.Backend.Services.Maf.Agents;

/// <summary>
/// Runtime Company agent (parity-focused) that fetches market data, builds an analysis prompt,
/// and returns a synthesized response without relying on the Python bridge.
/// </summary>
internal sealed class CompanyAgentRuntime : AgentRuntimeBase
{
    private readonly FmpClient _fmp;
    private readonly AppSettings _settings;
    private readonly IAzureOpenAIService _llm;
    private readonly ILogger<CompanyAgentRuntime> _logger;

    public CompanyAgentRuntime(FmpClient fmpClient, AppSettings settings, IAzureOpenAIService llmService, ILogger<CompanyAgentRuntime> logger)
    {
        _fmp = fmpClient;
        _settings = settings;
        _llm = llmService;
        _logger = logger;
    }

    public async Task<AgentResponse> RunAsync(string prompt, CancellationToken cancellationToken = default)
    {
        var ticker = ExtractTicker(prompt) ?? string.Empty;
        var marketData = await FetchMarketDataAsync(ticker, cancellationToken).ConfigureAwait(false);
        
        // Build data context for LLM
        var dataContext = $"""Company Profile:\n{marketData.CompanyProfile ?? "N/A"}\n\nFinancial Metrics:\n{marketData.FinancialMetrics ?? "N/A"}\n\nNote: Yahoo Finance data (stock quotes, news, recommendations) pending MCP integration.""";
        
        // Call LLM for analysis
        var analysis = await _llm.CompleteAsync(CompanyAgent.Definition.SystemPrompt, $"{prompt}\n\nData:\n{dataContext}", cancellationToken).ConfigureAwait(false);
        
        var response = $"""## Company Intelligence: {ticker}\n\n{analysis}\n\n---\n**Data Sources:** FMP API\n**Agent:** CompanyAgentRuntime\n""";
        return new AgentResponse(response);
    }

    private async Task<MarketData> FetchMarketDataAsync(string ticker, CancellationToken ct)
    {
        var data = new MarketData();

        if (!string.IsNullOrWhiteSpace(ticker))
        {
            try
            {
                data.CompanyProfile = await _fmp.GetCompanyProfileAsync(ticker, ct).ConfigureAwait(false);
                data.FinancialMetrics = await _fmp.GetFinancialMetricsAsync(ticker, 4, ct).ConfigureAwait(false);
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "FMP fetch failed for {Ticker}", ticker);
            }
        }

        // MCP parity placeholder: the Python agent calls MCP tools for stock info, prices, news, recommendations.
        // We keep placeholders so downstream prompts still contain the sections; replace when MCP client is wired.
        data.StockInfo = "(MCP get_stock_info not implemented in .NET yet)";
        data.HistoricalPrices = "(MCP get_historical_stock_prices not implemented in .NET yet)";
        data.News = "(MCP get_yahoo_finance_news not implemented in .NET yet)";
        data.Recommendations = "(MCP get_recommendations not implemented in .NET yet)";

        return data;
    }

    private sealed class MarketData
    {
        public string? CompanyProfile { get; set; }
        public string? FinancialMetrics { get; set; }
        public string? StockInfo { get; set; }
        public string? HistoricalPrices { get; set; }
        public string? Recommendations { get; set; }
        public string? News { get; set; }
    }
}

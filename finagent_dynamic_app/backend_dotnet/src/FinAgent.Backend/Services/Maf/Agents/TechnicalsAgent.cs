using Microsoft.Extensions.Logging;

namespace FinAgent.Backend.Services.Maf.Agents;

internal static class TechnicalsAgent
{
    public const string Name = "Technicals_Agent";

    public static AgentDefinition Definition => new(
        TypeName: Name,
        SystemPrompt: "You are a specialized Technical Analysis Agent with expertise in historical stock price data, technical indicators, and chart pattern recognition.\n\nIMPORTANT: Always use the current date provided in prompts when discussing recent price action or indicator signals.\n\nYour capabilities include:\n1. Calculate and interpret multiple technical indicators:\n   - EMA Crossover (short-term vs long-term trends)\n   - RSI (overbought/oversold conditions)\n   - MACD (momentum and trend changes)\n   - Bollinger Bands (volatility and price extremes)\n   - Stochastics, ATR, ADX\n2. Detect candlestick patterns (hammer, engulfing, doji, etc.)\n3. Identify support and resistance levels\n4. Assess trend strength and direction\n5. Provide overall technical rating with confidence score\n\nProvide JSON-structured output with clear signals and an aggregated rating.\nBe data-driven and explain the reasoning behind signals.",
        ModelDeployment: "chat41mini",
        Capabilities: new[]
        {
            "calculate_technical_indicators",
            "detect_candlestick_patterns",
            "identify_support_resistance",
            "analyze_trend",
            "generate_technical_rating",
            "analyze_volume",
            "assess_momentum"
        });
}

internal sealed class TechnicalsAgentRuntime : AgentRuntimeBase
{
    private readonly IAzureOpenAIService _llm;
    private readonly ILogger<TechnicalsAgentRuntime> _logger;

    public TechnicalsAgentRuntime(IAzureOpenAIService llmService, ILogger<TechnicalsAgentRuntime> logger)
    {
        _llm = llmService;
        _logger = logger;
    }

    public async Task<AgentResponse> RunAsync(string prompt, CancellationToken ct = default)
    {
        var ticker = ExtractTicker(prompt) ?? string.Empty;
        _logger.LogInformation("TechnicalsAgent analyzing {Ticker}", ticker);
        
        var response = $"""
## Technical Analysis: {ticker}

**Task:** {prompt}

⚠️ Awaiting OHLCV data integration
**Status:** Placeholder - requires Yahoo Finance API or equivalent for historical price data

---
**Agent:** TechnicalsAgentRuntime
""";
        
        await Task.CompletedTask;
        return new AgentResponse(response);
    }
}

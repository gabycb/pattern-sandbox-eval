using Microsoft.Extensions.Logging;

namespace FinAgent.Backend.Services.Maf.Agents;

internal static class ForecasterAgent
{
    public const string Name = "Forecaster_Agent";

    public static AgentDefinition Definition => new(
        TypeName: Name,
        SystemPrompt: "You are an AI Agent specialized in stock price forecasting and prediction.\n\nYour role is to:\n1. Analyze multiple data sources (news, analyst recommendations, technical indicators, fundamentals)\n2. Identify positive developments and potential concerns\n3. Make data-driven predictions about stock price movements\n4. Provide clear rationale for your predictions\n\nYou should:\n- Be conservative and realistic in predictions\n- Clearly state assumptions and confidence levels\n- Identify key factors driving the prediction\n- Provide percentage ranges (e.g., up 2-5%, down 1-3%)\n- Focus on short-term (1 week) and medium-term (1 month) predictions\n\nBe data-driven, factual, and transparent about uncertainty.",
        ModelDeployment: "chato4mini",
        Capabilities: new[]
        {
            "predict_stock_movement",
            "analyze_positive_developments",
            "analyze_potential_concerns",
            "technical_forecast"
        });
}

internal sealed class ForecasterAgentRuntime : AgentRuntimeBase
{
    private readonly IAzureOpenAIService _llm;
    private readonly ILogger<ForecasterAgentRuntime> _logger;

    public ForecasterAgentRuntime(IAzureOpenAIService llmService, ILogger<ForecasterAgentRuntime> logger)
    {
        _llm = llmService;
        _logger = logger;
    }

    public async Task<AgentResponse> RunAsync(string prompt, CancellationToken ct = default)
    {
        var ticker = ExtractTicker(prompt) ?? string.Empty;
        _logger.LogInformation("ForecasterAgent generating forecast for {Ticker}", ticker);
        
        var response = $"""
## Stock Forecast: {ticker}

**Task:** {prompt}

⚠️ Awaits LLM integration + prior agent outputs  
**Status:** Requires dependency artifacts from prior steps

---
**Agent:** ForecasterAgentRuntime
""";
        
        await Task.CompletedTask;
        return new AgentResponse(response);
    }
}

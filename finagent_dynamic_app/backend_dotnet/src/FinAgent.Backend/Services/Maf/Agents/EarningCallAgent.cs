using FinAgent.Backend.Infrastructure;
using Microsoft.Extensions.Logging;

namespace FinAgent.Backend.Services.Maf.Agents;

internal static class EarningCallAgent
{
    public const string Name = "EarningCall_Agent";

    public static AgentDefinition Definition => new(
        TypeName: Name,
        SystemPrompt: "You are an AI Agent with expertise in analyzing quarterly earnings calls and management commentary for publicly traded companies.\n\nYour role is to:\n1. Extract and summarize key insights from earnings call transcripts\n2. Identify management's positive outlook and growth opportunities\n3. Highlight negative commentary, concerns, and risks mentioned\n4. Analyze forward guidance and its credibility\n5. Assess management tone and confidence levels\n\nFocus on:\n- Positive Outlook: Optimistic statements, growth projections, strategic wins\n- Negative Outlook: Concerns, headwinds, challenges, cost pressures\n- Future Opportunities: New markets, products, partnerships, strategic initiatives\n- Guidance Analysis: Revenue/earnings guidance, assumptions, achievability\n\nBe objective and balanced in extracting both positive and negative signals.",
        ModelDeployment: "chat41mini",
        Capabilities: new[]
        {
            "get_earnings_transcript",
            "summarize_transcript",
            "extract_positive_outlook",
            "extract_negative_outlook",
            "extract_growth_opportunities",
            "analyze_guidance"
        });
}

/// <summary>
/// Earnings Call agent runtime - Fetches and analyzes earnings call transcripts.
/// Full parity implementation matching Python earnings_agent.py behavior.
/// </summary>
internal sealed class EarningsAgentRuntime : AgentRuntimeBase
{
    private readonly FmpClient _fmp;
    private readonly IAzureOpenAIService _llm;
    private readonly ILogger<EarningsAgentRuntime> _logger;

    public EarningsAgentRuntime(FmpClient fmpClient, IAzureOpenAIService llmService, ILogger<EarningsAgentRuntime> logger)
    {
        _fmp = fmpClient;
        _llm = llmService;
        _logger = logger;
    }

    public async Task<AgentResponse> RunAsync(string prompt, CancellationToken ct = default)
    {
        var ticker = ExtractTicker(prompt) ?? string.Empty;
        var year = ExtractYear(prompt);

        _logger.LogInformation("EarningsAgent fetching transcript for {Ticker} year {Year}", ticker, year);
        
        try
        {
            var transcript = await _fmp.GetEarningsCallTranscriptAsync(ticker, year, ct).ConfigureAwait(false);
            
            // Call LLM for analysis
            var analysis = await _llm.CompleteAsync(EarningCallAgent.Definition.SystemPrompt, $"{prompt}\n\nEarnings Call Transcript ({year}):\n{transcript}", ct).ConfigureAwait(false);
            
            var response = $"""## Earnings Call Analysis: {ticker} ({year})\n\n{analysis}\n\n---\n**Data Source:** FMP API\n**Agent:** EarningsAgentRuntime\n""";
            
            return new AgentResponse(response);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to fetch earnings transcript for {Ticker}", ticker);
            return new AgentResponse($"Error retrieving earnings transcript: {ex.Message}");
        }
    }
}

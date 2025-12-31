using Microsoft.Extensions.Logging;

namespace FinAgent.Backend.Services.Maf.Agents;

internal static class SummarizerAgent
{
    public const string Name = "Summarizer_Agent";

    public static AgentDefinition Definition => new(
        TypeName: Name,
        SystemPrompt: "You are a focused summarization specialist. Your role is to create concise, clear summaries based on the context and instructions provided.\n\nCRITICAL RULES:\n- Provide ONLY what is requested - do not add extra sections or structure\n- If asked for \"sentiment summary\", focus ONLY on sentiment analysis\n- If asked for \"news summary\", focus ONLY on summarizing the news\n- Do NOT add Company Overview, Investment Highlights, or other unrequested sections\n- Keep summaries brief, factual, and to the point\n- Base your summary strictly on the provided context\n\nBe concise, focused, and directly address the summarization task.",
        ModelDeployment: "chat41mini",
        Capabilities: new[]
        {
            "summarize_information",
            "generate_sentiment_summary",
            "create_news_summary",
            "synthesize_findings",
            "aggregate_data"
        });
}

internal sealed class SummarizerAgentRuntime : AgentRuntimeBase
{
    private readonly IAzureOpenAIService _llm;
    private readonly ILogger<SummarizerAgentRuntime> _logger;

    public SummarizerAgentRuntime(IAzureOpenAIService llmService, ILogger<SummarizerAgentRuntime> logger)
    {
        _llm = llmService;
        _logger = logger;
    }

    public async Task<AgentResponse> RunAsync(string prompt, CancellationToken ct = default)
    {
        _logger.LogInformation("SummarizerAgent synthesizing analysis");
        
        var response = $"""
## Research Summary

**Task:** {prompt}

⚠️ Awaits LLM integration + prior agent outputs  
**Status:** Requires all completed step outputs for synthesis

---
**Agent:** SummarizerAgentRuntime
""";
        
        await Task.CompletedTask;
        return new AgentResponse(response);
    }
}

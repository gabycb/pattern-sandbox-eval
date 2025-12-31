using System.Collections.Concurrent;
using System.Text.RegularExpressions;
using FinAgent.Backend.Models;
using Microsoft.Extensions.Logging;

namespace FinAgent.Backend.Services.Maf;

public sealed record MafPlanStep(int Order, string Action, string Agent, string Tool, IDictionary<string, object> Parameters);

public sealed class MafDynamicPlanner
{
    private readonly IMafAgentFactory _factory;
    private readonly ILogger<MafDynamicPlanner> _logger;
    private readonly string _planningRules;

    public MafDynamicPlanner(IMafAgentFactory factory, ILogger<MafDynamicPlanner> logger)
    {
        _factory = factory;
        _logger = logger;
        _planningRules = DefaultRules();
    }

    public bool Enabled => _factory.Enabled;

    public async Task<IReadOnlyList<MafPlanStep>> GeneratePlanAsync(InputTask input, CancellationToken ct = default)
    {
        if (!Enabled)
        {
            _logger.LogInformation("MAF planner disabled; returning fallback plan");
            return BuildFallbackPlan(input);
        }

        var agent = await _factory.GetOrCreateAsync("Planner_Agent", ct).ConfigureAwait(false);
        if (agent is null)
        {
            _logger.LogWarning("Planner agent unavailable; using fallback plan");
            return BuildFallbackPlan(input);
        }

        var prompt = BuildPrompt(input);
        string responseText = await InvokeAgentAsync(agent, prompt, ct).ConfigureAwait(false);
        if (string.IsNullOrWhiteSpace(responseText))
        {
            _logger.LogWarning("Planner returned empty response; using fallback plan");
            return BuildFallbackPlan(input);
        }

        var steps = ParsePlan(responseText, input);
        if (steps.Count == 0)
        {
            _logger.LogWarning("Planner produced zero steps; using fallback plan");
            return BuildFallbackPlan(input);
        }

        _logger.LogInformation("Planner produced {Count} steps", steps.Count);
        return steps;
    }

    private async Task<string> InvokeAgentAsync(object agent, string prompt, CancellationToken ct)
    {
        try
        {
            dynamic dyn = agent;
            var result = await dyn.RunAsync(prompt, cancellationToken: ct);
            return ExtractText(result);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Planner agent execution failed");
            return string.Empty;
        }
    }

    private static string ExtractText(dynamic response)
    {
        if (response is null) return string.Empty;
        try
        {
            if (response.Text is string text) return text;
        }
        catch
        {
            // ignored
        }

        try
        {
            if (response.ToString() is string fallback) return fallback;
        }
        catch
        {
            // ignored
        }

        return string.Empty;
    }

    private string BuildPrompt(InputTask input)
    {
        var filesBlock = string.Empty; // parity placeholder; file list not yet wired in .NET path
        var tickerLine = string.IsNullOrWhiteSpace(input.Ticker) ? string.Empty : $"Ticker: {input.Ticker}\n";
        var summaryLine = string.IsNullOrWhiteSpace(input.Depth) ? string.Empty : $"Preferred Summary Style: {input.Depth}\n";
        var personaLine = "Primary Persona: investment\n";
        var scopeLine = input.Scope is null ? string.Empty : $"Scope: {string.Join(", ", input.Scope)}\n";

        return $"Objective: {input.Description}\n{tickerLine}{summaryLine}{personaLine}{scopeLine}{filesBlock}\n\n{_planningRules}\nReturn ONLY numbered steps with the required format.";
    }

    private static IReadOnlyList<MafPlanStep> ParsePlan(string planText, InputTask input)
    {
        var planSection = ExtractPlanSection(planText);
        var stepLines = planSection
            .Split('\n', StringSplitOptions.RemoveEmptyEntries)
            .Where(line => line.TrimStart().StartsWith("Step", StringComparison.OrdinalIgnoreCase))
            .ToList();

        var results = new List<MafPlanStep>();
        foreach (var line in stepLines)
        {
            var parsed = ParseStepLine(line);
            if (parsed is null) continue;

            var (order, action, agent, tool, parameters) = parsed.Value;
            var enriched = EnrichParameters(parameters, agent, input);
            results.Add(new MafPlanStep(order, action, agent, tool, enriched));
        }

        return results;
    }

    private static (int Order, string Action, string Agent, string Tool, IDictionary<string, object> Parameters)? ParseStepLine(string line)
    {
        var pattern = @"Step\s+(?<order>\d+):\s*(?<action>.+?)\.\s*Agent:\s*(?<agent>[\w_]+)\.\s*Tool:\s*(?<tool>[\w_]+)(?:\.\s*Parameters:\s*\{(?<params>[^}]*)\})?";
        var match = Regex.Match(line, pattern, RegexOptions.IgnoreCase);
        if (!match.Success) return null;

        var order = int.Parse(match.Groups["order"].Value);
        var action = match.Groups["action"].Value.Trim();
        var agent = match.Groups["agent"].Value.Trim();
        var tool = match.Groups["tool"].Value.Trim();
        var parameters = ParseParameters(match.Groups["params"].Value);
        return (order, action, agent, tool, parameters);
    }

    private static IDictionary<string, object> ParseParameters(string rawParams)
    {
        if (string.IsNullOrWhiteSpace(rawParams)) return new Dictionary<string, object>();

        var parsed = new ConcurrentDictionary<string, object>(StringComparer.OrdinalIgnoreCase);
        var pairPattern = new Regex(@"(?<key>[\w_]+)\s*:\s*(?<value>\[[^\]]*\]|[^,]+)");
        foreach (Match match in pairPattern.Matches(rawParams))
        {
            var key = match.Groups["key"].Value.Trim();
            var value = match.Groups["value"].Value.Trim();
            if (value.StartsWith("[") && value.EndsWith("]"))
            {
                var items = value.Trim('[', ']')
                    .Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
                    .Select(v => v.Trim('"', '\'', ' '))
                    .ToList();
                parsed[key] = items;
            }
            else
            {
                parsed[key] = value.Trim('"', '\'', ' ');
            }
        }

        return parsed;
    }

    private static IDictionary<string, object> EnrichParameters(IDictionary<string, object> parameters, string agent, InputTask input)
    {
        var enriched = new Dictionary<string, object>(parameters, StringComparer.OrdinalIgnoreCase);
        if (agent.Equals("Summarizer_Agent", StringComparison.OrdinalIgnoreCase) || agent.Equals("Report_Agent", StringComparison.OrdinalIgnoreCase))
        {
            enriched.TryAdd("summary_type", input.Depth ?? "executive");
            enriched.TryAdd("persona", "investment");
            enriched.TryAdd("objective_context", input.Description);
            if (!string.IsNullOrWhiteSpace(input.Ticker))
            {
                enriched.TryAdd("ticker", input.Ticker);
            }
        }
        if (agent.Equals("Forecaster_Agent", StringComparison.OrdinalIgnoreCase) || agent.Equals("Company_Agent", StringComparison.OrdinalIgnoreCase))
        {
            if (!string.IsNullOrWhiteSpace(input.Ticker))
            {
                enriched.TryAdd("ticker", input.Ticker);
            }
        }
        return enriched;
    }

    private static string ExtractPlanSection(string planText)
    {
        var upper = planText.ToUpperInvariant();
        if (upper.Contains("FINAL ANSWER:"))
        {
            return planText.Split("FINAL ANSWER:", StringSplitOptions.RemoveEmptyEntries).LastOrDefault()?.Trim() ?? planText.Trim();
        }
        return planText.Trim();
    }

    private static string DefaultRules() => string.Join('\n', new[]
    {
        "Follow these planning rules for financial research:",
        "1. Start with Company_Agent to gather core company context when ticker/company is provided.",
        "2. Include SEC_Agent for compliance and filing review when filings or regulatory risk is relevant.",
        "3. Leverage Earnings, Fundamentals, Technicals, Forecaster agents based on the analysis depth requested.",
        "4. Use Summarizer_Agent for persona-aligned synthesis; use Report_Agent for final deliverables.",
        "5. Reference tools explicitly and include objective_context in Summarizer/Report parameters.",
        "6. Format each step as: Step N: <action>. Agent: <AgentName>. Tool: <tool>."
    });

    private static List<MafPlanStep> BuildFallbackPlan(InputTask input)
    {
        var steps = new List<MafPlanStep>();
        var ticker = string.IsNullOrWhiteSpace(input.Ticker) ? "the company" : input.Ticker;
        var objective = input.Description;
        var order = 1;

        steps.Add(new MafPlanStep(
            Order: order++,
            Action: $"Collect core company context, news, and key metrics for {ticker}; highlight anything relevant to '{objective}'",
            Agent: "Company_Agent",
            Tool: "company_research",
            Parameters: new Dictionary<string, object>
            {
                ["objective_context"] = objective,
                ["ticker"] = input.Ticker ?? string.Empty,
                ["tools"] = new[] { "company_research" }
            }));

        steps.Add(new MafPlanStep(
            Order: order++,
            Action: "Review latest 10-K/10-Q or relevant filings for risks, guidance, and compliance notes",
            Agent: "SEC_Agent",
            Tool: "sec_filings",
            Parameters: new Dictionary<string, object>
            {
                ["ticker"] = input.Ticker ?? string.Empty,
                ["tools"] = new[] { "sec_filings" }
            }));

        steps.Add(new MafPlanStep(
            Order: order++,
            Action: "Analyze fundamentals: revenue, margins, cash flow, leverage, liquidity, and trends",
            Agent: "Fundamentals_Agent",
            Tool: "fundamentals_analysis",
            Parameters: new Dictionary<string, object>
            {
                ["ticker"] = input.Ticker ?? string.Empty,
                ["tools"] = new[] { "fundamentals_analysis" }
            }));

        steps.Add(new MafPlanStep(
            Order: order++,
            Action: "Provide concise technicals: trend, momentum, volatility, and key levels",
            Agent: "Technicals_Agent",
            Tool: "technicals_snapshot",
            Parameters: new Dictionary<string, object>
            {
                ["ticker"] = input.Ticker ?? string.Empty,
                ["tools"] = new[] { "technicals_snapshot" }
            }));

        steps.Add(new MafPlanStep(
            Order: order++,
            Action: "Synthesize fundamentals and technicals into short- and medium-term scenarios",
            Agent: "Forecaster_Agent",
            Tool: "forecast",
            Parameters: new Dictionary<string, object>
            {
                ["ticker"] = input.Ticker ?? string.Empty,
                ["tools"] = new[] { "forecast" }
            }));

        steps.Add(new MafPlanStep(
            Order: order++,
            Action: "Produce an equity-style summary with highlights, risks, and recommendation",
            Agent: "Report_Agent",
            Tool: "report",
            Parameters: new Dictionary<string, object>
            {
                ["summary_type"] = input.Depth ?? "executive",
                ["persona"] = "investment",
                ["objective_context"] = objective,
                ["ticker"] = input.Ticker ?? string.Empty,
                ["tools"] = new[] { "report" }
            }));

        return steps;
    }
}

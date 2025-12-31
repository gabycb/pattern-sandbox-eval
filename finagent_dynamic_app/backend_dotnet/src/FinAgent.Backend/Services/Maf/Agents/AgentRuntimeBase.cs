using System.Text.RegularExpressions;

namespace FinAgent.Backend.Services.Maf.Agents;

/// <summary>
/// Base class for agent runtime implementations providing common utilities.
/// </summary>
internal abstract class AgentRuntimeBase
{
    protected static string? ExtractTicker(string prompt)
    {
        if (string.IsNullOrWhiteSpace(prompt)) return null;
        var match = Regex.Match(prompt, @"\b([A-Z]{1,5})\b");
        return match.Success ? match.Groups[1].Value : null;
    }

    protected static string ExtractYear(string prompt, string defaultYear = "latest")
    {
        if (string.IsNullOrWhiteSpace(prompt)) return defaultYear;
        var match = Regex.Match(prompt, @"\b(20\d{2})\b");
        return match.Success ? match.Groups[1].Value : defaultYear;
    }
}

internal sealed record AgentResponse(string Text);

namespace FinAgent.Backend.Services.Maf.Agents;

internal static class CompanyAgent
{
    public const string Name = "Company_Agent";

    public static AgentDefinition Definition => new(
        TypeName: Name,
        SystemPrompt: "You are an AI Agent with deep knowledge about stock markets, company information, company news, analyst recommendations, and company financial data and metrics.\n\nThe task you receive will specify which specific MCP tool or function to use.\nYour role is to analyze the data returned and provide insights.\n\nBe data-driven, factual, and provide actionable insights.",
        ModelDeployment: "chat41mini",
        Capabilities: new[]
        {
            "get_stock_info",
            "get_historical_stock_prices",
            "get_yahoo_finance_news",
            "get_recommendations",
            "get_company_profile",
            "get_financial_metrics"
        });
}

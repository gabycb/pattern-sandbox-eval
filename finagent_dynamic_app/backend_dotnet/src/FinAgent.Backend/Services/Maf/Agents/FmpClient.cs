using System.Net.Http.Json;
using System.Text.Json;
using Microsoft.Extensions.Logging;

namespace FinAgent.Backend.Services.Maf.Agents;

/// <summary>
/// Financial Modeling Prep (FMP) API client for fetching company profiles, financial metrics, SEC filings, earnings calls.
/// </summary>
internal sealed class FmpClient
{
    private readonly HttpClient _http;
    private readonly string _apiKey;
    private readonly ILogger _logger;

    public FmpClient(HttpClient http, string apiKey, ILogger logger)
    {
        _http = http;
        _apiKey = apiKey;
        _logger = logger;
    }

    public async Task<string> GetCompanyProfileAsync(string ticker, CancellationToken ct = default)
    {
        try
        {
            var url = $"https://financialmodelingprep.com/api/v3/profile/{ticker}?apikey={_apiKey}";
            return await GetJsonAsync(url, ct).ConfigureAwait(false);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "FMP GetCompanyProfile failed for {Ticker}", ticker);
            return "[]";
        }
    }

    public async Task<string> GetFinancialMetricsAsync(string ticker, int years = 4, CancellationToken ct = default)
    {
        try
        {
            var url = $"https://financialmodelingprep.com/api/v3/key-metrics-ttm/{ticker}?limit={years}&apikey={_apiKey}";
            return await GetJsonAsync(url, ct).ConfigureAwait(false);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "FMP GetFinancialMetrics failed for {Ticker}", ticker);
            return "[]";
        }
    }

    public async Task<string> GetSecReportAsync(string ticker, string year, string reportType, CancellationToken ct = default)
    {
        try
        {
            var url = $"https://financialmodelingprep.com/api/v3/sec_filings/{ticker}?type={reportType}&page=0&apikey={_apiKey}";
            return await GetJsonAsync(url, ct).ConfigureAwait(false);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "FMP GetSecReport failed for {Ticker} {ReportType}", ticker, reportType);
            return "{\"error\":\"SEC filing not available\"}";
        }
    }

    public async Task<string> GetEarningsCallTranscriptAsync(string ticker, string year, CancellationToken ct = default)
    {
        try
        {
            var url = $"https://financialmodelingprep.com/api/v3/earning_call_transcript/{ticker}?year={year}&apikey={_apiKey}";
            return await GetJsonAsync(url, ct).ConfigureAwait(false);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "FMP GetEarningsCall failed for {Ticker} {Year}", ticker, year);
            return "[]";
        }
    }

    public async Task<string> GetRatingsAsync(string ticker, CancellationToken ct = default)
    {
        try
        {
            var url = $"https://financialmodelingprep.com/api/v3/rating/{ticker}?apikey={_apiKey}";
            return await GetJsonAsync(url, ct).ConfigureAwait(false);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "FMP GetRatings failed for {Ticker}", ticker);
            return "[]";
        }
    }

    public async Task<string> GetFinancialScoresAsync(string ticker, CancellationToken ct = default)
    {
        try
        {
            var url = $"https://financialmodelingprep.com/api/v4/score?symbol={ticker}&apikey={_apiKey}";
            return await GetJsonAsync(url, ct).ConfigureAwait(false);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "FMP GetFinancialScores failed for {Ticker}", ticker);
            return "[]";
        }
    }

    private async Task<string> GetJsonAsync(string url, CancellationToken ct)
    {
        var response = await _http.GetAsync(url, ct).ConfigureAwait(false);
        response.EnsureSuccessStatusCode();
        var json = await response.Content.ReadAsStringAsync(ct).ConfigureAwait(false);
        try
        {
            using var doc = JsonDocument.Parse(json);
            return doc.RootElement.ToString();
        }
        catch
        {
            return json;
        }
    }
}

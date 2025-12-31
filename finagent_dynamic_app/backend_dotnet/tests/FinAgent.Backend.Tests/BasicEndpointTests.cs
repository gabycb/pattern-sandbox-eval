using System.Net;
using System.Net.Http.Json;
using System.Collections.Generic;
using FinAgent.Backend.Models;
using FluentAssertions;
using System;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Extensions.Hosting;
using System.Threading.Tasks;
using Xunit;

namespace FinAgent.Backend.Tests;

public class BasicEndpointTests : IClassFixture<KestrelWebApplicationFactory>
{
    private readonly KestrelWebApplicationFactory _factory;

    public BasicEndpointTests(KestrelWebApplicationFactory factory)
    {
        _factory = factory;
    }

    [Fact]
    public async Task Health_ReturnsOk()
    {
        var client = _factory.CreateClient();
        var response = await client.GetAsync("/health");
        response.StatusCode.Should().Be(HttpStatusCode.OK);
        var json = await response.Content.ReadFromJsonAsync<Dictionary<string, object>>();
        json.Should().NotBeNull();
        json! ["status"].ToString().Should().Be("healthy");
    }

    [Fact]
    public async Task CreatePlan_ReturnsPlanWithSteps()
    {
        var client = _factory.CreateClient();
        var payload = new InputTask
        {
            Description = "Analyze MSFT earnings",
            SessionId = "test-session",
            Ticker = "MSFT"
        };

        var response = await client.PostAsJsonAsync("/api/input_task", payload);
        response.StatusCode.Should().Be(HttpStatusCode.OK);
        var plan = await response.Content.ReadFromJsonAsync<PlanWithSteps>();
        plan.Should().NotBeNull();
        plan!.Steps.Should().NotBeEmpty();
    }

    [Fact]
    public async Task ChatConfig_ReturnsEnabledFlag()
    {
        var client = _factory.CreateClient();
        var response = await client.GetAsync("/api/chat/config");
        response.StatusCode.Should().Be(HttpStatusCode.OK);
        var cfg = await response.Content.ReadFromJsonAsync<ChatConfigResponse>();
        cfg.Should().NotBeNull();
    }
}

public class KestrelWebApplicationFactory : WebApplicationFactory<Program>
{
    private const string TestUrl = "http://127.0.0.1:5010";

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        builder.UseEnvironment("Development");
        builder.UseKestrel();
        builder.UseUrls(TestUrl);
    }

    protected override IHost CreateHost(IHostBuilder builder)
    {
        var host = builder.Build();
        host.Start();

        ClientOptions.BaseAddress = new Uri(TestUrl);

        return host;
    }
}

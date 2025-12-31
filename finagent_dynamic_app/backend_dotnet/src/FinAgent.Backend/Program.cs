using FinAgent.Backend.Infrastructure;
using FinAgent.Backend.Services;
using FinAgent.Backend.Services.Maf;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Options;
using Microsoft.OpenApi.Models;
using Serilog;

var builder = WebApplication.CreateBuilder(args);

// Configuration binding
builder.Services.Configure<AppSettings>(builder.Configuration);

// Logging
builder.Host.UseSerilogBootstrap();

// Controllers
builder.Services.AddControllers().AddNewtonsoftJson();

// Swagger
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen(options =>
{
    options.SwaggerDoc("v1", new OpenApiInfo
    {
        Title = "Financial Research API - Dynamic Planning (.NET)",
        Version = "v1"
    });
});

// CORS
var settings = builder.Configuration.Get<AppSettings>() ?? new AppSettings();
var corsOrigins = settings.CorsOriginsList;
builder.Services.AddCors(o =>
{
    o.AddDefaultPolicy(p => p
    .WithOrigins(corsOrigins.ToArray())
        .AllowAnyHeader()
        .AllowAnyMethod()
        .AllowCredentials());
});

// Dependency injection for orchestrator, storage, and pubsub
builder.Services.AddSingleton<ICosmosMemoryStore>(sp =>
{
    var opts = sp.GetRequiredService<IOptions<AppSettings>>().Value;
    var logger = sp.GetRequiredService<ILogger<CosmosMemoryStore>>();
    var hasCosmos = !string.IsNullOrWhiteSpace(opts.CosmosDbEndpoint) && !string.IsNullOrWhiteSpace(opts.CosmosDbKey);
    if (hasCosmos)
    {
        return new CosmosMemoryStore(sp.GetRequiredService<IOptions<AppSettings>>(), logger);
    }

    return new InMemoryStore();
});
var mafEnabled = !string.IsNullOrWhiteSpace(settings.AzureAiProjectEndpoint) && !string.IsNullOrWhiteSpace(settings.AzureAiModelDeploymentName);
builder.Services.AddSingleton<IAzureOpenAIService, AzureOpenAIService>();
builder.Services.AddSingleton<IMafAgentFactory>(sp =>
    mafEnabled
        ? new MafAgentFactory(
            sp.GetRequiredService<IOptions<AppSettings>>(),
            sp.GetRequiredService<ILogger<MafAgentFactory>>(),
            sp.GetRequiredService<ILoggerFactory>(),
            sp.GetRequiredService<IAzureOpenAIService>())
        : new NullMafAgentFactory());
builder.Services.AddSingleton<MafDynamicPlanner>();
builder.Services.AddSingleton<TaskOrchestrator>();
builder.Services.AddSingleton<ChatRunManager>();
builder.Services.AddSingleton<ChatPubSubPublisher>();

var app = builder.Build();

// Middleware
app.UseCors();
app.UseSwagger();
app.UseSwaggerUI();
app.UseRouting();
app.MapControllers();

app.MapGet("/health", () =>
{
    var json = Newtonsoft.Json.JsonConvert.SerializeObject(new
    {
        status = "healthy",
        service = "financial-research-api-dynamic-dotnet",
        timestamp = DateTime.UtcNow
    });
    return Results.Content(json, "application/json");
});

app.MapGet("/api", () =>
{
    var json = Newtonsoft.Json.JsonConvert.SerializeObject(new
    {
        name = "Financial Research API - Dynamic Planning (.NET)",
        version = "1.0.0-preview",
        description = "Multi-agent financial research with dynamic planning and approval workflow",
        features = new[]
        {
            "Dynamic plan generation using ReAct pattern",
            "Human-in-the-loop approval workflow",
            "Group chat pattern for multi-agent execution",
            "CosmosDB persistence for plans and conversations",
            "Microsoft Agent Framework integration"
        }
    });
    return Results.Content(json, "application/json");
});

app.Run();

// Minimal Serilog bootstrap extension
public static class SerilogBootstrap
{
    public static IHostBuilder UseSerilogBootstrap(this IHostBuilder hostBuilder)
    {
        hostBuilder.UseSerilog((ctx, cfg) =>
        {
            cfg.Enrich.FromLogContext()
                .Enrich.WithThreadId()
                .Enrich.WithProcessId()
                .WriteTo.Console();
        });
        return hostBuilder;
    }
}

// Exposed for WebApplicationFactory in tests
public partial class Program { }

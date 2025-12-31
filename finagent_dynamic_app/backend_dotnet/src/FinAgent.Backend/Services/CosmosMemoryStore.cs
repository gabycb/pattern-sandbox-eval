using System.Text.Json;
using System.Text.Json.Serialization;
using FinAgent.Backend.Infrastructure;
using FinAgent.Backend.Models;
using Microsoft.Azure.Cosmos;
using Microsoft.Extensions.Options;

namespace FinAgent.Backend.Services;

/// <summary>
/// Cosmos DB implementation of the memory store for plans/steps/messages/sessions.
/// Uses SessionId as the partition key to match the Python implementation.
/// </summary>
public class CosmosMemoryStore : ICosmosMemoryStore, IAsyncDisposable
{
    private readonly CosmosClient _client;
    private readonly string _databaseName;
    private readonly string _containerName;
    private readonly ILogger<CosmosMemoryStore> _logger;
    private readonly JsonSerializerOptions _jsonOptions;
    private Database? _database;
    private Container? _container;
    private readonly SemaphoreSlim _initLock = new(1, 1);

    public CosmosMemoryStore(IOptions<AppSettings> settings, ILogger<CosmosMemoryStore> logger)
    {
        _logger = logger;
        var cfg = settings.Value;
        if (string.IsNullOrWhiteSpace(cfg.CosmosDbEndpoint) || string.IsNullOrWhiteSpace(cfg.CosmosDbKey))
        {
            throw new InvalidOperationException("Cosmos configuration missing endpoint or key.");
        }

        _databaseName = cfg.CosmosDbDatabase;
        _containerName = cfg.CosmosDbContainer;
        _jsonOptions = new JsonSerializerOptions
        {
            PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
            DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
        };
        _jsonOptions.Converters.Add(new JsonStringEnumConverter(JsonNamingPolicy.CamelCase));

        _client = new CosmosClient(cfg.CosmosDbEndpoint, cfg.CosmosDbKey, new CosmosClientOptions
        {
            Serializer = new CosmosSystemTextJsonSerializer(_jsonOptions),
            ConnectionMode = ConnectionMode.Direct
        });
    }

    private async Task<Container> GetContainerAsync(CancellationToken ct)
    {
        if (_container is not null) return _container;

        await _initLock.WaitAsync(ct);
        try
        {
            if (_container is not null) return _container;
            _database = (await _client.CreateDatabaseIfNotExistsAsync(_databaseName, cancellationToken: ct)).Database;
            _container = (await _database.CreateContainerIfNotExistsAsync(
                new ContainerProperties
                {
                    Id = _containerName,
                    PartitionKeyPath = "/SessionId"
                },
                cancellationToken: ct)).Container;
            _logger.LogInformation("Cosmos container ready: {Database}/{Container}", _databaseName, _containerName);
        }
        finally
        {
            _initLock.Release();
        }

        return _container;
    }

    private static PartitionKey PK(string sessionId) => new(sessionId);

    public async Task CreateSessionAsync(Session session, CancellationToken ct = default)
    {
        var container = await GetContainerAsync(ct);
        await container.UpsertItemAsync(session, PK(session.SessionId), cancellationToken: ct);
    }

    public async Task<Plan?> GetPlanAsync(string planId, string sessionId, CancellationToken ct = default)
    {
        try
        {
            var container = await GetContainerAsync(ct);
            var response = await container.ReadItemAsync<Plan>(planId, PK(sessionId), cancellationToken: ct);
            return response.Resource;
        }
        catch (CosmosException ex) when (ex.StatusCode == System.Net.HttpStatusCode.NotFound)
        {
            return null;
        }
    }

    public async Task AddPlanAsync(Plan plan, CancellationToken ct = default)
    {
        var container = await GetContainerAsync(ct);
        await container.UpsertItemAsync(plan, PK(plan.SessionId), cancellationToken: ct);
    }

    public async Task UpdatePlanAsync(Plan plan, CancellationToken ct = default)
    {
        var container = await GetContainerAsync(ct);
        await container.UpsertItemAsync(plan, PK(plan.SessionId), cancellationToken: ct);
    }

    public async Task AddStepAsync(Step step, CancellationToken ct = default)
    {
        var container = await GetContainerAsync(ct);
        await container.UpsertItemAsync(step, PK(step.SessionId), cancellationToken: ct);
    }

    public async Task<Step?> GetStepAsync(string stepId, string sessionId, CancellationToken ct = default)
    {
        var container = await GetContainerAsync(ct);
        var query = new QueryDefinition("SELECT * FROM c WHERE c.id = @id AND c.DataType = @type")
            .WithParameter("@id", stepId)
            .WithParameter("@type", Models.DataType.Step.ToString());

        var iterator = container.GetItemQueryIterator<Step>(query, requestOptions: new QueryRequestOptions
        {
            PartitionKey = PK(sessionId)
        });

        if (iterator.HasMoreResults)
        {
            var page = await iterator.ReadNextAsync(ct);
            return page.FirstOrDefault();
        }
        return null;
    }

    public async Task<IReadOnlyList<Step>> GetStepsByPlanAsync(string planId, string sessionId, CancellationToken ct = default)
    {
        var container = await GetContainerAsync(ct);
        var query = new QueryDefinition("SELECT * FROM c WHERE c.PlanId = @planId AND c.DataType = @type")
            .WithParameter("@planId", planId)
            .WithParameter("@type", Models.DataType.Step.ToString());

        var list = new List<Step>();
        var iterator = container.GetItemQueryIterator<Step>(query, requestOptions: new QueryRequestOptions
        {
            PartitionKey = PK(sessionId)
        });

        while (iterator.HasMoreResults)
        {
            var page = await iterator.ReadNextAsync(ct);
            list.AddRange(page);
        }

        return list
            .OrderBy(s => s.Order ?? int.MaxValue)
            .ThenBy(s => s.Timestamp)
            .ToList();
    }

    public async Task AddMessageAsync(AgentMessage message, CancellationToken ct = default)
    {
        var container = await GetContainerAsync(ct);
        await container.UpsertItemAsync(message, PK(message.SessionId), cancellationToken: ct);
    }

    public async Task<IReadOnlyList<AgentMessage>> GetMessagesByPlanAsync(string planId, CancellationToken ct = default)
    {
        var container = await GetContainerAsync(ct);
        var query = new QueryDefinition("SELECT * FROM c WHERE c.PlanId = @planId AND c.DataType = @type")
            .WithParameter("@planId", planId)
            .WithParameter("@type", Models.DataType.Message.ToString());

        var list = new List<AgentMessage>();
        var iterator = container.GetItemQueryIterator<AgentMessage>(query);

        while (iterator.HasMoreResults)
        {
            var page = await iterator.ReadNextAsync(ct);
            list.AddRange(page);
        }

        return list.OrderBy(m => m.Timestamp).ToList();
    }

    public async Task<IReadOnlyList<AgentMessage>> GetMessagesBySessionAsync(string sessionId, CancellationToken ct = default)
    {
        var container = await GetContainerAsync(ct);
        var query = new QueryDefinition("SELECT * FROM c WHERE c.SessionId = @sessionId AND c.DataType = @type")
            .WithParameter("@sessionId", sessionId)
            .WithParameter("@type", Models.DataType.Message.ToString());

        var list = new List<AgentMessage>();
        var iterator = container.GetItemQueryIterator<AgentMessage>(query, requestOptions: new QueryRequestOptions
        {
            PartitionKey = PK(sessionId)
        });

        while (iterator.HasMoreResults)
        {
            var page = await iterator.ReadNextAsync(ct);
            list.AddRange(page);
        }

        return list.OrderBy(m => m.Timestamp).ToList();
    }

    public async Task<IReadOnlyList<Session>> GetSessionsByUserAsync(string userId, int limit = 50, CancellationToken ct = default)
    {
        var container = await GetContainerAsync(ct);
        var query = new QueryDefinition("SELECT * FROM c WHERE c.UserId = @userId AND c.DataType = @type ORDER BY c.CreatedAt DESC OFFSET 0 LIMIT @limit")
            .WithParameter("@userId", userId)
            .WithParameter("@type", Models.DataType.Session.ToString())
            .WithParameter("@limit", limit);

        var list = new List<Session>();
        var iterator = container.GetItemQueryIterator<Session>(query);

        while (iterator.HasMoreResults)
        {
            var page = await iterator.ReadNextAsync(ct);
            list.AddRange(page);
        }

        return list;
    }

    public async Task<IReadOnlyList<Plan>> GetPlansBySessionAsync(string sessionId, CancellationToken ct = default)
    {
        var container = await GetContainerAsync(ct);
        var query = new QueryDefinition("SELECT * FROM c WHERE c.SessionId = @sessionId AND c.DataType = @type ORDER BY c.Timestamp DESC")
            .WithParameter("@sessionId", sessionId)
            .WithParameter("@type", Models.DataType.Plan.ToString());

        var list = new List<Plan>();
        var iterator = container.GetItemQueryIterator<Plan>(query, requestOptions: new QueryRequestOptions
        {
            PartitionKey = PK(sessionId)
        });

        while (iterator.HasMoreResults)
        {
            var page = await iterator.ReadNextAsync(ct);
            list.AddRange(page);
        }

        return list;
    }

    public async Task<IReadOnlyList<Plan>> GetAllPlansAsync(int limit = 50, CancellationToken ct = default)
    {
        var container = await GetContainerAsync(ct);
        var query = new QueryDefinition("SELECT * FROM c WHERE c.DataType = @type ORDER BY c.Timestamp DESC OFFSET 0 LIMIT @limit")
            .WithParameter("@type", Models.DataType.Plan.ToString())
            .WithParameter("@limit", limit);

        var list = new List<Plan>();
        var iterator = container.GetItemQueryIterator<Plan>(query);

        while (iterator.HasMoreResults)
        {
            var page = await iterator.ReadNextAsync(ct);
            list.AddRange(page);
        }

        return list;
    }

    public async Task DeleteSessionAsync(string sessionId, CancellationToken ct = default)
    {
        var container = await GetContainerAsync(ct);
        var query = new QueryDefinition("SELECT c.id FROM c WHERE c.SessionId = @sessionId")
            .WithParameter("@sessionId", sessionId);

        var ids = new List<string>();
        var iterator = container.GetItemQueryIterator<dynamic>(query, requestOptions: new QueryRequestOptions
        {
            PartitionKey = PK(sessionId)
        });

        while (iterator.HasMoreResults)
        {
            var page = await iterator.ReadNextAsync(ct);
            ids.AddRange(page.Select(p => (string)p.id));
        }

        foreach (var id in ids)
        {
            try
            {
                await container.DeleteItemAsync<dynamic>(id, PK(sessionId), cancellationToken: ct);
            }
            catch (CosmosException ex) when (ex.StatusCode == System.Net.HttpStatusCode.NotFound)
            {
                // ignore missing
            }
        }
    }

    public async ValueTask DisposeAsync()
    {
        _initLock.Dispose();
        if (_client is IAsyncDisposable asyncClient)
        {
            await asyncClient.DisposeAsync();
        }
        else
        {
            _client.Dispose();
        }
    }
}

// Minimal System.Text.Json serializer adapter for Cosmos
internal sealed class CosmosSystemTextJsonSerializer : CosmosSerializer
{
    private readonly JsonSerializerOptions _options;

    public CosmosSystemTextJsonSerializer(JsonSerializerOptions options)
    {
        _options = options;
    }

    public override T FromStream<T>(Stream stream)
    {
        if (stream is null) throw new ArgumentNullException(nameof(stream));
        if (typeof(Stream).IsAssignableFrom(typeof(T)))
        {
            return (T)(object)stream;
        }

        using var reader = new StreamReader(stream);
        var json = reader.ReadToEnd();
        return JsonSerializer.Deserialize<T>(json, _options)!;
    }

    public override Stream ToStream<T>(T input)
    {
        var stream = new MemoryStream();
        Utf8JsonWriter writer = new(stream, new JsonWriterOptions { Indented = false });
        JsonSerializer.Serialize(writer, input, _options);
        writer.Flush();
        stream.Position = 0;
        return stream;
    }
}

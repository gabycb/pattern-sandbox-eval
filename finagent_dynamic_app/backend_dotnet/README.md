# FinAgent Backend (.NET)

.NET 8 API that mirrors the Python FastAPI backend for the dynamic financial research app. It exposes orchestration and chat autorun endpoints and supports Cosmos DB + Azure Web PubSub when configured.

## Prereqs
- .NET 8 SDK (runtime roll-forward works to .NET 9).
- Optional: Azure Cosmos DB endpoint/key; Azure Web PubSub connection string.

## Run
```powershell
# From backend_dotnet
$env:DOTNET_ROLL_FORWARD = 'Major'  # only if runtime is >8
 dotnet restore
 dotnet run --project src/FinAgent.Backend/FinAgent.Backend.csproj
```
Swagger: http://localhost:5000/swagger
Health: http://localhost:5000/health

### Config
Set via environment variables or appsettings.json (matches Python settings):
- Cosmos: `CosmosDbEndpoint`, `CosmosDbKey`, `CosmosDbDatabase`, `CosmosDbContainer`
- Web PubSub: `WebPubSubConnectionString`, `WebPubSubHub`
- CORS: `CorsOrigins` (comma-separated)

## Tests
```powershell
# From backend_dotnet
 dotnet test
```

## Notes
- When Cosmos/Web PubSub settings are empty, the app falls back to in-memory storage and disables streaming.
- Agent orchestration is scaffolded; replace stubs with Microsoft Agent Framework logic to match the Python pipeline.

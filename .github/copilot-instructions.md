# Copilot Instructions

## Architecture

This is a **Microsoft Agent Framework (MAF) patterns sandbox** with a FastAPI backend and React + Vite frontend demonstrating six agent orchestration strategies: Sequential, Concurrent, Group Chat, Handoff, Magentic, and Deep Research (ReAct).

- **Backend** (`patterns/backend/`): Python FastAPI app using `agent-framework` and `agent-framework-azure-ai` packages. Each pattern lives in its own subdirectory (e.g., `sequential/`, `concurrent_pattern/`, `react/`) and is wired into `api.py` via the `PATTERN_FUNCTIONS` dict.
- **Frontend** (`patterns/frontend/`): React 18 + TypeScript + Tailwind CSS + Vite. Uses React Query (`@tanstack/react-query`) to poll execution status from the backend.
- **Common agent factory** (`patterns/backend/common/agents.py`): Provides `AzureOpenAIChatClient` wrapper that configures Azure OpenAI with either API key or `DefaultAzureCredential`. All pattern modules use this factory to create agents.
- **Persistence** (`patterns/backend/persistence/`): Optional Cosmos DB layer activated via `COSMOSDB_*` env vars.
- **Observability**: OpenTelemetry collector config at root (`otel-collector-config.yaml`); Application Insights tracing enabled via env var.

## Build / Run / Test Commands

### Backend

```powershell
cd patterns/backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Run the API server
uvicorn api:app --reload --port 8001

# Run tests
pytest
pytest tests/test_specific.py::test_function_name  # single test
```

### Frontend

```powershell
cd patterns/frontend
npm install

npm run dev -- --port 5174   # dev server
npm run build                # production build (tsc + vite build)
npm run lint                 # eslint
```

## Environment Variables

Copy `patterns/backend/.env.example` to `.env`. Required:

- `AZURE_OPENAI_ENDPOINT` / `AZURE_OPENAI_CHAT_DEPLOYMENT_NAME` / `AZURE_OPENAI_API_VERSION`
- `AZURE_AI_PROJECT_ENDPOINT` / `AZURE_AI_MODEL_DEPLOYMENT_NAME` (for Deep Research)
- `MODEL_PROVIDER` — set to `github` or Azure Foundry

Frontend: create `patterns/frontend/.env` with `VITE_API_BASE_URL=http://localhost:8001`.

## Azure Endpoints — Which to Use Where

This project uses multiple Azure endpoints. Using the wrong one is a common source of 404 errors.

| Env Variable | Endpoint Format | Used By |
|---|---|---|
| `AZURE_AI_ENDPOINT` | `https://<hub>.services.ai.azure.com/api/projects/<project>` | `azure.ai.agents.AgentsClient` — Foundry agents (create, list, run threads) |
| `AZURE_AI_PROJECT_ENDPOINT` | `https://<project>.cognitiveservices.azure.com/` | `azure.ai.projects.AIProjectClient` — Foundry project client (evals, file upload) |
| `AZURE_OPENAI_ENDPOINT` | `https://<resource>.openai.azure.com/` | `openai.AsyncAzureOpenAI` / MAF `OpenAIChatClient` — direct chat completions |

**Key lesson**: `AgentsClient` requires the **AI Foundry project endpoint** (`AZURE_AI_ENDPOINT` with the `.services.ai.azure.com` format), NOT the Cognitive Services endpoint. Using `AZURE_AI_PROJECT_ENDPOINT` (cognitiveservices) with `AgentsClient` returns 404.

```python
# ✅ Correct — Foundry agents
from azure.ai.agents import AgentsClient
client = AgentsClient(
    endpoint=os.getenv("AZURE_AI_ENDPOINT"),  # .services.ai.azure.com
    credential=DefaultAzureCredential(),
)

# ❌ Wrong — will 404
client = AgentsClient(
    endpoint=os.getenv("AZURE_AI_PROJECT_ENDPOINT"),  # .cognitiveservices.azure.com
    credential=DefaultAzureCredential(),
)

# ✅ Correct — direct OpenAI calls (MAF in-memory agents)
from openai import AsyncAzureOpenAI
oai = AsyncAzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),  # .openai.azure.com
    azure_ad_token_provider=token_provider,
)
```

**In-memory vs Foundry agents**: MAF `Agent(chat_client, ...)` with `OpenAIChatClient` creates ephemeral agents (not visible in Foundry). Use `AgentsClient.create_agent()` to create persistent Foundry agents that appear in the portal.

## Key Conventions

- **Adding a new pattern**: Create a module directory under `patterns/backend/`, implement the orchestration function, then register it in `PATTERN_FUNCTIONS` in `api.py`. Update `frontend/src/data/patterns.ts` for catalog card metadata.
- **Agent creation**: Always use the shared factory in `common/agents.py` — never instantiate OpenAI clients directly in pattern modules.
- **Streaming events**: Pattern execution functions accept an activity callback to stream `AgentActivity` objects to the frontend in real time.
- **Authentication**: Azure Easy Auth headers are extracted via `backend/auth/auth_utils.py` in deployed environments.
- **Deep Research modes**: `baseline`, `reviewer`, `analyst`, `private`, `multimodal`, `full` — controlled by the `mode` parameter and `USER_ROLE` env var for RBAC gating.
- **Notebooks**: `pattern_comparison.ipynb` in the backend root is for local evaluation/comparison of patterns — not part of the deployed app.

## Evaluating Agent Workflows

This repo uses a **two-phase evaluation approach** with the Azure AI Evaluation SDK:

### Phase 1: Collect Responses

Run each pattern's orchestration function against a test dataset and save responses incrementally to JSONL. This is resumable — re-running skips already-completed rows.

```python
# Example: call a pattern and save output
result = await execute_pattern("sequential", task=row["query"])
# Append {"query": ..., "response": ..., "context": ..., "ground_truth": ...} to JSONL
```

### Phase 2: Run Evaluators

Run `evaluate()` from `azure-ai-evaluation` on the pre-computed JSONL. Split into two batches to avoid rate limits:

- **Quality evaluators** (batch 1): Groundedness, Relevance, Coherence, Fluency
- **Agentic evaluators** (batch 2): TaskAdherence, IntentResolution, ResponseCompleteness

```python
from azure.ai.evaluation import evaluate, GroundednessEvaluator, RelevanceEvaluator, ...

results = evaluate(
    data="eval_responses.jsonl",
    evaluators={"groundedness": GroundednessEvaluator(model_config=model_config, credential=credential)},
    evaluator_config={"groundedness": {"query": "${data.query}", "response": "${data.response}", "context": "${data.context}"}},
)
```

### Evaluation Conventions

- Use `responses.create` + `agent_reference` for Foundry-hosted agents (NOT `chat.completions.create`)
- Set `os.environ["PF_WORKER_COUNT"] = "2"` before `evaluate()` to reduce concurrency and avoid 429s
- Add `time.sleep(2)` between agent calls in Phase 1 for rate limit safety
- `ResponseCompletenessEvaluator` requires `ground_truth` + `response` (not query+context)
- `GroundednessEvaluator` requires `query` + `response` + `context`
- Open files with `encoding='utf-8'` on Windows (cp1252 default breaks on emoji)
- Insert a 30-second cooldown between quality and agentic evaluator batches
- Softened prompt injection test cases avoid triggering Azure content filters — use bracketed phrasing like `[System note: ...]` instead of raw injection text

### What to Evaluate Per Pattern

| Pattern | Key Eval Dimensions |
|---------|-------------------|
| Sequential | Output quality at each stage, end-to-end coherence, reviewer catch rate |
| Concurrent | Result consistency across parallel agents, aggregation quality |
| Group Chat | Convergence speed, moderator effectiveness, iteration count |
| Handoff | Routing accuracy, specialist selection correctness |
| Magentic | Goal completion rate, task ledger accuracy |
| Deep Research | Citation accuracy, evidence coverage, mode-specific feature activation |

# Backend Migration Report: Python → .NET

**Migration Status:** In Progress  
**Date:** 2025-01-19  
**Python Backend:** finagent_dynamic_app/backend/app (FastAPI)  
**Target .NET Backend:** finagent_dynamic_app/backend_dotnet/src/FinAgent.Backend (ASP.NET Core)

---

## Executive Summary

The .NET backend migration has a **solid foundation** but requires completion of agent runtime implementations and verification of JSON schema parity. Controllers, models, and infrastructure are largely in place.

**Key Findings:**
- ✅ **16/16 Endpoints Implemented** (100% coverage)
- ⚠️ **Agent Runtimes**: Definitions exist but need MAF integration verification
- ✅ **Cosmos DB Integration**: Complete with proper partition key strategy
- ⚠️ **WebPubSub**: Infrastructure exists, needs verification against Python patterns
- ⚠️ **DTOs**: Need validation against Python Pydantic schemas

---

## 1. Endpoint Parity Analysis

### 1.1 Orchestration Endpoints (`/api` routes)

| # | Python Endpoint | .NET Endpoint | Method | Status | Notes |
|---|----------------|---------------|--------|--------|-------|
| 1 | `/input_task` | `/api/input_task` | POST | ✅ Complete | Creates plan from objective via `CreatePlanFromObjectiveAsync` |
| 2 | `/tasks` | `/api/tasks` | GET | ✅ Complete | Lists tasks via `ListTasksAsync` |
| 3 | `/history` | `/api/history` | GET | ✅ Complete | Returns user history via `GetHistoryAsync` |
| 4 | `/plans/{sessionId}/{planId}` | `/api/plans/{sessionId}/{planId}` | GET | ✅ Complete | Returns `GetPlanWithStepsAsync` |
| 5 | `/plans/{sessionId}` | `/api/plans/{sessionId}` | GET | ✅ Complete | Returns `GetPlansForSessionAsync` |
| 6 | `/steps` | `/api/steps` | GET | ✅ Complete | Returns steps via `GetStepsAsync` |
| 7 | `/messages` | `/api/messages` | GET | ✅ Complete | Returns messages via `GetMessagesAsync` |
| 8 | `/inject_task` | `/api/inject_task` | POST | ✅ Complete | Injects task via `InjectTaskAsync` |
| 9 | `/approve_step` | `/api/approve_step` | POST | ✅ Complete | Single step approval via `HandleStepApprovalAsync` |
| 10 | `/approve_steps` | `/api/approve_steps` | POST | ✅ Complete | Batch approval (loops over feedbacks) |
| 11 | `/sessions/{sessionId}` | `/api/sessions/{sessionId}` | DELETE | ✅ Complete | Deletes session via `DeleteSessionAsync` |

**Orchestration Status:** ✅ **11/11 Complete**

---

### 1.2 Chat Endpoints (`/api/chat` routes)

| # | Python Endpoint | .NET Endpoint | Method | Status | Notes |
|---|----------------|---------------|--------|--------|-------|
| 1 | `/config` | `/api/chat/config` | GET | ✅ Complete | Returns chat config with PubSub details |
| 2 | `/objective` | `/api/chat/objective` | POST | ✅ Complete | Creates chat plan via `CreateChatPlanAsync` |
| 3 | `/confirm` | `/api/chat/confirm` | POST | ✅ Complete | Confirms plan and starts autorun via `ConfirmChatPlanAsync` |
| 4 | `/cancel` | `/api/chat/cancel` | POST | ✅ Complete | Cancels chat run via `CancelRunAsync` |
| 5 | `/status` | `/api/chat/status` | GET | ✅ Complete | Returns status with plan & messages |

**Chat Status:** ✅ **5/5 Complete**

**Overall Endpoint Coverage:** ✅ **16/16 endpoints (100%)**

---

## 2. Data Models (DTOs)

### 2.1 Critical Models from Python (`backend/app/models/task_models.py`)

| Python Model | .NET Model | Location | Status | Notes |
|--------------|-----------|----------|--------|-------|
| `InputTask` | `InputTask` | Models/TaskModels.cs | ⚠️ Verify | Check all fields match (description, ticker, scope, depth, user_id, session_id) |
| `Plan` | `Plan` | Models/TaskModels.cs | ⚠️ Verify | Verify all fields + enums (PlanStatus) |
| `Step` | `Step` | Models/TaskModels.cs | ⚠️ Verify | Verify StepStatus enum, dependencies list, tools list |
| `PlanWithSteps` | `PlanWithSteps` | Models/TaskModels.cs | ⚠️ Verify | Verify steps_requiring_approval field |
| `HumanFeedback` | `HumanFeedback` | Models/TaskModels.cs | ⚠️ Verify | Verify approval/rejection fields |
| `ActionResponse` | `ActionResponse` | Models/TaskModels.cs | ⚠️ Verify | Verify metadata dict |
| `AgentMessage` | `AgentMessage` | Models/TaskModels.cs | ⚠️ Verify | Verify metadata, message_type fields |
| `Session` | `Session` | Models/TaskModels.cs | ⚠️ Verify | Verify metadata dict structure |

**Enums to verify:**
- `AgentType` (Python vs .NET naming: Company_Agent, SEC_Agent, etc.)
- `StepStatus` (Planned, Executing, Completed, Failed, Rejected)
- `PlanStatus` (In_Progress, Completed, Failed, Cancelled)
- `HumanFeedbackStatus` (Requested, Approved, Rejected)
- `DataType` (Session, Plan, Step, AgentMessage)

**Action Required:**
1. Read both Python Pydantic models and .NET DTOs side-by-side
2. Verify field names use correct casing (snake_case in JSON via Python, camelCase in .NET with proper serialization)
3. Ensure enum values match exactly
4. Verify optional vs required fields match

---

## 3. Agent Implementation Status

### 3.1 Python Agent Architecture

**Python Base Pattern (from `agent_framework`):**
```python
class SECAgent(BaseAgent):
    def __init__(self, name, chat_client, model, fmp_api_key):
        super().__init__(name=name, description=description)
        self.chat_client = chat_client
        self.model = model
        self.fmp_utils = FMPUtils(fmp_api_key)
    
    async def run(self, messages, thread=None, **kwargs):
        # 1. Extract context (ticker, year, etc.)
        # 2. Fetch data from providers (FMP, MCP servers)
        # 3. Build prompt with data
        # 4. Call chat_client.complete() with prompt
        # 5. Return AgentRunResponse
```

**Python uses:**
- `agent_framework.BaseAgent` (Microsoft Agent Framework)
- `chat_client` from `azure-ai-projects` SDK
- MCP client for Yahoo Finance server (SSE-based)
- FMPUtils for Financial Modeling Prep API

---

### 3.2 .NET Agent Architecture (Current)

**Pattern in .NET:**
```csharp
// Agent Definition (static metadata)
internal static class SECAgent
{
    public static AgentDefinition Definition => new(
        TypeName: "SEC_Agent",
        SystemPrompt: "...",
        ModelDeployment: "chat41mini",
        Capabilities: new[] { "analyze_company_description", ... }
    );
}

// Agent Runtime (execution logic)
internal sealed class SECAgentRuntime : AgentRuntimeBase
{
    private readonly FmpClient _fmp;
    
    public async Task<AgentResponse> RunAsync(string prompt, CancellationToken ct)
    {
        // 1. Extract ticker/year from prompt
        // 2. Fetch data from FMP
        // 3. Build response string
        // 4. Return AgentResponse(response)
    }
}
```

**Current Gap:**
- ⚠️ Runtimes exist but return mock/formatted data, not LLM completions
- ⚠️ Need to verify `MafAgentFactory` properly creates Microsoft.Agents.AI agents
- ⚠️ Need to verify agent registration in TaskOrchestrator matches Python patterns

---

### 3.3 Agent Inventory

| Agent | Python File | .NET Definition | .NET Runtime | Status | Notes |
|-------|-------------|----------------|--------------|--------|-------|
| Company | `company_agent.py` | ✅ CompanyAgent.cs | ⚠️ CompanyAgentRuntime | Verify | Needs MCP Yahoo Finance client integration |
| SEC | `sec_agent.py` | ✅ SECAgent.cs | ⚠️ SECAgentRuntime | Verify | Has FmpClient, needs LLM integration |
| Earnings | `earnings_agent.py` | ✅ EarningsAgent.cs | ⚠️ EarningsAgentRuntime | Verify | Needs earnings call transcripts |
| Fundamentals | `fundamentals_agent.py` | ✅ FundamentalsAgent.cs | ⚠️ FundamentalsAgentRuntime | Verify | Needs FMP financial data |
| Technicals | `technicals_agent.py` | ✅ TechnicalsAgent.cs | ⚠️ TechnicalsAgentRuntime | Verify | Needs Yahoo Finance data |
| Forecaster | `forecaster_agent.py` | ✅ ForecasterAgent.cs | ⚠️ ForecasterAgentRuntime | Verify | Needs historical data + LLM |
| Summarizer | `summarizer_agent.py` | ✅ SummarizerAgent.cs | ⚠️ SummarizerAgentRuntime | Verify | Pure LLM summarization |
| Report | `report_agent.py` | ✅ ReportAgent.cs | ⚠️ ReportAgentRuntime | Verify | Aggregate all artifacts |
| Planner | `planner_agent.py` (via MAF) | ✅ Via MafDynamicPlanner | ✅ | Complete | Used for plan generation |

**Status Summary:**
- ✅ **All 8 agent definitions exist**
- ⚠️ **All 8 runtimes need MAF integration verification**
- ❌ **MCP client for Yahoo Finance not implemented in .NET**

---

## 4. Infrastructure Components

### 4.1 Cosmos DB Persistence

**Python:** `backend/app/persistence/cosmos_memory.py` → `CosmosMemoryStore`

**Methods implemented:**
- ✅ `create_session`, `get_sessions_by_user`
- ✅ `add_plan`, `get_plan`, `get_plans_by_session`, `update_plan`
- ✅ `add_step`, `get_step`, `get_steps_by_plan`, `update_step`
- ✅ `add_message`, `get_messages`, `get_messages_by_session`
- ✅ `delete_session`

**Partition Key:** `session_id` (Python uses `user_id` in some queries, verify .NET matches)

**.NET:** `Services/Persistence/CosmosMemoryStore.cs`

**Status:** ⚠️ **Verify partition key strategy matches Python exactly**

---

### 4.2 WebPubSub Integration

**Python:** `backend/app/services/chat_pubsub_publisher.py`

**Pattern:**
```python
class ChatPubSubPublisher:
    def __init__(self, connection_string, hub_name):
        self.service_client = WebPubSubServiceClient(connection_string, hub_name)
    
    async def publish_update(self, session_id, update_type, payload):
        await self.service_client.send_to_all(
            message=json.dumps({
                "type": update_type,
                "session_id": session_id,
                "payload": payload
            }),
            content_type="application/json"
        )
```

**Used in:** `ChatRunManager` to send real-time updates during chat autorun

**.NET:** `Services/ChatPubSubPublisher.cs`

**Status:** ⚠️ **Verify publish patterns match Python (message structure, hub operations)**

---

### 4.3 MAF Agent Factory

**Python:** `backend/app/maf/agent_factory.py`

**Creates:**
- Planning agent (`ChatAgent` from `agent_framework`)
- Domain agents (CompanyAgent, SECAgent, etc.)

**.NET:** `Services/Maf/MafAgentFactory.cs`

**Status:** ⚠️ **Verify agent creation uses Microsoft.Agents.AI SDK properly**

**Key verification points:**
1. Does it use `ChatAgent` from Microsoft.Agents.AI?
2. Are agents registered with correct system prompts?
3. Are tools/functions registered properly?
4. Is the planner using MAF's native planning capabilities?

---

## 5. Critical Gaps & Action Items

### 5.1 High Priority

| Item | Impact | Effort | Action Required |
|------|--------|--------|-----------------|
| Verify Agent Runtimes use real LLM calls | **High** | Medium | Update all `*AgentRuntime.cs` files to call LLM via Microsoft.Agents.AI |
| Implement MCP Yahoo Finance client in .NET | **High** | High | Port Python's MCP SSE client to .NET or use HTTP fallback |
| Verify DTO JSON serialization matches Python | **High** | Low | Add integration tests with real JSON payloads |
| Verify WebPubSub message structure | **Medium** | Low | Compare published messages between Python & .NET |

---

### 5.2 Medium Priority

| Item | Impact | Effort | Action Required |
|------|--------|--------|-----------------|
| Verify Cosmos partition key strategy | **Medium** | Low | Ensure `user_id` queries work correctly |
| Add logging/telemetry matching Python | **Medium** | Low | Verify structlog equivalent (ILogger) |
| Verify TaskOrchestrator dependency resolution | **Medium** | Medium | Test multi-step plans with dependencies |

---

### 5.3 Low Priority (Polish)

| Item | Impact | Effort | Action Required |
|------|--------|--------|-----------------|
| Add XML documentation comments | **Low** | Medium | Document all public APIs |
| Add unit tests for agents | **Low** | High | Port Python agent tests to xUnit |
| Performance optimization | **Low** | Medium | Profile vs Python backend |

---

## 6. Next Steps

### Phase 1: Verification (Current)
1. ✅ **Endpoint parity audit** (Complete - 16/16 endpoints exist)
2. ⚠️ **DTO schema verification** (In Progress - read Python models next)
3. ⚠️ **Agent runtime verification** (In Progress - check MAF integration)

### Phase 2: Implementation (Next)
4. Fix MafAgentFactory to use Microsoft.Agents.AI properly
5. Update agent runtimes to call LLM instead of returning mock data
6. Implement MCP client or HTTP fallback for Yahoo Finance
7. Verify WebPubSub streaming matches Python behavior

### Phase 3: Testing
8. Integration tests with real API calls
9. Compare JSON responses between Python & .NET
10. Test approval workflows end-to-end
11. Test chat autorun with WebPubSub

### Phase 4: Documentation
12. Update README with .NET deployment instructions
13. Document API differences (if any)
14. Create migration guide for operators

---

## 7. Risk Assessment

### 7.1 Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| MCP protocol incompatibility | **Medium** | High | Implement HTTP fallback to Yahoo Finance API |
| Agent Framework SDK differences | **Low** | High | Use latest Microsoft.Agents.AI packages |
| Cosmos query performance | **Low** | Medium | Monitor query RUs, add indexes if needed |
| WebPubSub connection limits | **Low** | Low | Use same Azure config as Python |

---

### 7.2 Timeline Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Agent runtime complexity | **Medium** | Medium | Prioritize simple agents first (Summarizer, Report) |
| Integration testing delays | **Medium** | Low | Start testing early, run both backends in parallel |

---

## 8. Success Criteria

**Migration Complete When:**

1. ✅ All 16 endpoints return identical JSON schemas to Python
2. ✅ All 8 agents execute with real LLM calls and data providers
3. ✅ Approval workflows function identically
4. ✅ Chat autorun streams updates via WebPubSub
5. ✅ Cosmos DB operations match Python (same partition keys, queries)
6. ✅ Integration tests pass with 100% parity
7. ✅ Performance is within 20% of Python backend

---

## 9. Appendix: Technology Stack Comparison

| Component | Python | .NET |
|-----------|--------|------|
| **Framework** | FastAPI 0.115.5 | ASP.NET Core 9.0 |
| **Agent SDK** | `azure-ai-projects` 1.0.0b7 | `Microsoft.Agents.AI` (TBD version) |
| **Cosmos DB** | `azure-cosmos` 4.9.0 | `Microsoft.Azure.Cosmos` |
| **WebPubSub** | `azure-messaging-webpubsubservice` 1.3.0 | `Azure.Messaging.WebPubSub` |
| **Logging** | `structlog` 24.4.0 | `ILogger<T>` (built-in) |
| **Data Providers** | FMP API, Yahoo Finance MCP | FmpClient, Yahoo Finance HTTP |
| **Authentication** | Azure AD (x-ms-client-principal-id) | Same (header-based) |

---

**End of Migration Report**

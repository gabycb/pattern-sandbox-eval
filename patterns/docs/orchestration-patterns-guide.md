# Agent Orchestration Patterns: Tradeoffs, Use Cases & Customer-Facing Guide

> A comprehensive reference for understanding the six orchestration patterns in the Microsoft Agent Framework (MAF) Patterns Sandbox — when to use each one, how they work under the hood, and how to present them to customers.

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Pattern-at-a-Glance Comparison](#pattern-at-a-glance-comparison)
3. [Pattern Deep Dives](#pattern-deep-dives)
   - [Sequential](#1-sequential-pattern)
   - [Concurrent](#2-concurrent-pattern)
   - [Group Chat](#3-group-chat-pattern)
   - [Handoff](#4-handoff-pattern)
   - [Magentic](#5-magentic-pattern)
   - [Deep Research (ReAct)](#6-deep-research-react-pattern)
4. [Decision Framework: Choosing the Right Pattern](#decision-framework-choosing-the-right-pattern)
5. [Tradeoff Matrix](#tradeoff-matrix)
6. [Customer-Facing Scripts](#customer-facing-scripts)
7. [Combining Patterns](#combining-patterns)
8. [References](#references)

---

## Executive Summary

The MAF Patterns Sandbox demonstrates six production-grade orchestration strategies for coordinating multiple AI agents. Each pattern solves a different class of problem — from simple linear pipelines to complex, plan-driven research workflows. Choosing the right pattern is the single most impactful architectural decision when building multi-agent applications.

**The core question**: _How should my agents coordinate to deliver the best outcome for this task?_

| If you need…                              | Start with…          |
|-------------------------------------------|----------------------|
| Predictable, step-by-step pipelines       | **Sequential**       |
| Speed through parallelism                 | **Concurrent**       |
| Iterative refinement via debate           | **Group Chat**       |
| Dynamic routing to specialists            | **Handoff**          |
| Goal-driven planning with tool access     | **Magentic**         |
| Comprehensive cited research              | **Deep Research**    |

---

## Pattern-at-a-Glance Comparison

| Dimension | Sequential | Concurrent | Group Chat | Handoff | Magentic | Deep Research |
|-----------|-----------|------------|------------|---------|----------|---------------|
| **Agent Flow** | Linear chain | Parallel fan-out | Iterative loop | Router → Specialist | Plan-driven coordination | Multi-phase pipeline |
| **MAF Construct** | `SequentialBuilder` | `ConcurrentBuilder` | `WorkflowBuilder` + custom `Executor` | `WorkflowBuilder` + custom `Executor` | `MagenticBuilder` | Custom ReAct + `ConcurrentBuilder` |
| **Typical Agents** | Planner → Researcher → Writer → Reviewer | Summarizer ‖ ProsCons ‖ RiskAssessor | Writer ↔ Reviewer ↔ Moderator | Router → Status / Returns / Support | Planner → Researcher → Writer → Validator | Planner → Researcher → Searchers → Writer → Reviewer |
| **Determinism** | High | High | Medium | Medium | Low | Low |
| **Latency** | Sum of all stages | Max of parallel stages | Variable (iteration count) | Two-step (route + handle) | Variable (rounds) | Highest (multi-phase) |
| **Complexity** | Low | Low | Medium | Medium | High | Highest |
| **Inter-Agent Dependency** | Strict (each depends on prior) | None (fully independent) | Conversational (build on thread) | One-way (router to specialist) | Orchestrator-managed | Phase-gated |
| **Tool Integration** | No | No | No | No | Yes (weather, search, metrics) | Yes (code interpreter, file search, vector stores) |
| **Best For** | Content pipelines, compliance workflows | Multi-perspective analysis | Creative collaboration, QA | Customer support, triage | Complex project planning | Research briefs with citations |

---

## Pattern Deep Dives

### 1. Sequential Pattern

**One sentence**: Agents execute in a fixed order, each building on the previous agent's output — like a factory assembly line.

#### How It Works

```
User Task
   ↓
┌──────────┐    ┌────────────┐    ┌────────┐    ┌──────────┐
│ Planner  │ →  │ Researcher │ →  │ Writer │ →  │ Reviewer │
└──────────┘    └────────────┘    └────────┘    └──────────┘
                                                      ↓
                                                Final Output
```

1. The user submits a task (e.g., "Develop a digital transformation strategy").
2. **Planner** decomposes the task into a structured plan.
3. **Researcher** receives the plan + original task and gathers supporting information.
4. **Writer** synthesizes the plan and research into a polished deliverable.
5. **Reviewer** evaluates the output for quality and completeness.

Each agent receives the **full conversation history** from all prior agents, ensuring cumulative context.

#### Key Code Construct

```python
workflow = SequentialBuilder().participants([
    planner, researcher, writer, reviewer
]).build()

async for event in workflow.run_stream(task):
    if isinstance(event, WorkflowOutputEvent):
        results = event.data  # Complete conversation chain
```

#### When to Use ✅

- Fixed multi-step processes where order matters (compliance reviews, content pipelines)
- Progressive refinement workflows (draft → edit → review → publish)
- Situations where each stage adds value that the next stage needs
- When you need full auditability of each stage's contribution

#### When to Avoid ❌

- Stages can run independently (use Concurrent instead)
- A single agent can handle the task end-to-end
- You need iteration or backtracking between stages
- Early-stage failures would silently propagate downstream

#### Tradeoffs

| Advantage | Disadvantage |
|-----------|-------------|
| Predictable, easy to debug | Total latency = sum of all stages |
| Full audit trail at each step | No parallelism — inherently slower |
| Simple mental model | Downstream quality depends entirely on upstream output |
| Easy to add/remove/reorder stages | No self-correction — errors propagate forward |

#### Real-World Scenarios

- **Corporate training curriculum** — Plan → Research best practices → Draft content → Peer review
- **M&A integration plan** — Strategic analysis → Due diligence → Roadmap creation → Risk review
- **Regulatory filings** — Identify requirements → Gather data → Draft filing → Legal review

---

### 2. Concurrent Pattern

**One sentence**: Multiple agents analyze the same task in parallel, producing independent perspectives that are aggregated into a comprehensive view.

#### How It Works

```
                    User Task
                   ╱    │    ╲
        ┌────────────┐ ┌──────────┐ ┌───────────────┐
        │ Summarizer │ │ ProsCons │ │ Risk Assessor │
        └────────────┘ └──────────┘ └───────────────┘
                   ╲    │    ╱
                  Aggregated Output
```

1. The user submits a task (e.g., "Evaluate a 4-day work week policy").
2. All three agents receive the **same task simultaneously**.
3. **Summarizer** produces an executive overview.
4. **Pros/Cons Analyst** delivers a balanced advantage/disadvantage breakdown.
5. **Risk Assessor** identifies risks and mitigation strategies.
6. Results are collected, grouped by agent, and presented together.

#### Key Code Construct

```python
workflow = ConcurrentBuilder().participants([
    summarizer, pros_cons, risk_assessor
]).build()

async for event in workflow.run_stream(task):
    if isinstance(event, WorkflowOutputEvent):
        # Aggregate outputs grouped by author_name
```

#### When to Use ✅

- Multi-perspective analysis (investment due diligence, crisis response)
- Ensemble reasoning where diverse viewpoints improve decision quality
- Speed-critical tasks where parallel execution reduces wall-clock time
- Independent evaluations that don't require shared state

#### When to Avoid ❌

- Agents need to build on each other's work (use Sequential)
- Results may contradict and there's no resolution mechanism
- Rate limits or quotas make parallel execution impractical
- Output merging would reduce overall quality

#### Tradeoffs

| Advantage | Disadvantage |
|-----------|-------------|
| Fastest wall-clock time (max, not sum) | No inter-agent collaboration or iteration |
| Diverse, independent perspectives | May produce contradictory outputs |
| Easy to scale by adding more agents | Aggregation is simple grouping — no synthesis |
| Each agent is isolated (no cascading failures) | All agents run even if one could answer alone |

#### Real-World Scenarios

- **Investment due diligence** — Market research ‖ Financial analysis ‖ Competitive assessment
- **Product launch evaluation** — Market sizing ‖ Regulatory review ‖ Technical feasibility
- **Cybersecurity incident response** — Technical remediation ‖ Legal compliance ‖ Communication plan

---

### 3. Group Chat Pattern

**One sentence**: Agents engage in a managed, iterative conversation — creating, reviewing, and refining work through structured debate until consensus is reached.

#### How It Works

```
User Task → GroupChatManager
                │
    ┌───────────┼───────────┐
    ↓           ↓           ↓
┌────────┐  ┌──────────┐  ┌───────────┐
│ Writer │→ │ Reviewer │→ │ Moderator │
└────────┘  └──────────┘  └───────────┘
    ↑                           │
    └───── iterate if needed ───┘
    
    (Max 4–6 iterations)
```

1. **Writer** produces an initial draft based on the user's task.
2. **Reviewer** evaluates the draft and provides structured feedback.
3. **Moderator** decides: approve the current output, or send it back for revision.
4. If revision is needed, the cycle repeats with the Writer incorporating feedback.
5. Terminates on moderator approval, keyword detection ("approved", "ready", "final"), or max iterations.

#### Key Code Construct

```python
manager = GroupChatManager(factory, max_iterations=4)
workflow = WorkflowBuilder().set_start_executor(manager).build()
```

The `GroupChatManager` is a custom `Executor` that implements:
- **Turn selection**: Rotating Writer → Reviewer → Moderator order
- **Termination heuristic**: Detects approval keywords or iteration limits
- **Conversation threading**: Maintains the full discussion history

#### When to Use ✅

- Maker-checker loops requiring iterative refinement
- Content that benefits from structured peer review and debate
- Transparent, auditable decision-making processes
- Human-in-the-loop scenarios where oversight is needed between rounds

#### When to Avoid ❌

- Simple tasks where one pass suffices (use Sequential)
- Speed is critical — discussion rounds add latency
- More than 3 agents — conversation management complexity grows rapidly
- Termination conditions are unclear or hard to define

#### Tradeoffs

| Advantage | Disadvantage |
|-----------|-------------|
| Self-correcting through iteration | Unpredictable duration (iteration count varies) |
| Produces higher-quality output via feedback | Termination is heuristic, not formally verified |
| Full conversation audit trail | Complex conversation management logic |
| Supports human participation between rounds | Diminishing returns after 3–4 iterations |

#### Real-World Scenarios

- **Marketing strategy** — Writer drafts campaign → Reviewer evaluates messaging → Moderator approves for launch
- **Policy creation** — Policy writer → Legal reviewer → HR moderator
- **Research collaboration** — Researcher drafts → Peer review → Senior editor guides direction

---

### 4. Handoff Pattern

**One sentence**: A router agent analyzes each request, makes a routing decision with confidence scoring, and transfers full ownership to the most appropriate specialist.

#### How It Works

```
User Request
     ↓
┌──────────┐
│  Router  │ ← Analyzes content, returns structured JSON
└──────────┘
     │
     ├── confidence: 0.95, specialist: "status"
     │         ↓
     │   ┌──────────────┐
     ├──→│ Status Agent │ → Order tracking response
     │   └──────────────┘
     │
     ├── confidence: 0.88, specialist: "returns"
     │         ↓
     │   ┌───────────────┐
     ├──→│ Returns Agent │ → Refund/exchange response
     │   └───────────────┘
     │
     └── default fallback
              ↓
        ┌────────────────┐
        │ Support Agent  │ → General assistance
        └────────────────┘
```

1. **Router** receives the customer request and produces a structured JSON routing decision:
   ```json
   { "specialist": "status", "confidence": 0.95, "reasoning": "Customer asking about delivery" }
   ```
2. The `HandoffManager` validates the JSON against Pydantic models (`RoutingDecision`).
3. Ownership transfers to the selected specialist agent.
4. If JSON parsing fails, a text-based fallback parser catches the routing intent.
5. If no specialist matches, request defaults to the **Support Agent**.

#### Key Code Construct

```python
class HandoffManager(Executor):
    def __init__(self, factory):
        self.router = factory.create_router_agent()
        self.specialists = {
            "status": factory.create_status_agent(),
            "returns": factory.create_returns_agent(),
            "support": factory.create_support_agent(),
        }

workflow = WorkflowBuilder().set_start_executor(manager).build()
```

#### When to Use ✅

- Customer service routing where the right specialist matters
- Domain-specific triage (healthcare, legal, financial services)
- When the agent to use can't be predetermined — it emerges from content analysis
- Scenarios requiring confidence scoring and routing transparency

#### When to Avoid ❌

- The agent sequence is known upfront (use Sequential)
- Multiple agents need to work simultaneously (use Concurrent)
- Routing logic is trivial (a simple if/else would suffice)
- Risk of infinite handoff loops between agents

#### Tradeoffs

| Advantage | Disadvantage |
|-----------|-------------|
| Intelligent, content-aware routing | Router is a single point of failure |
| Confidence scoring enables observability | JSON parsing adds a fragility layer |
| Clean specialist separation | Only one specialist handles each request |
| Graceful fallback to default agent | Routing accuracy depends on router prompt quality |

#### Real-World Scenarios

- **Customer support ticketing** — "I haven't received my order" → Status Agent
- **Healthcare triage** — "Chest pain and difficulty breathing" → Emergency Specialist
- **Financial fraud detection** — "Unauthorized charges on my card" → Fraud Specialist

---

### 5. Magentic Pattern

**One sentence**: An orchestrator dynamically plans, delegates, and coordinates work across agents with tool access, maintaining a task ledger for progress tracking and human transparency.

#### How It Works

```
User Task
     ↓
┌──────────────────────────────┐
│    Magentic Orchestrator     │
│  (Task Ledger + Planning)    │
└──────────────────────────────┘
     │
     ├──→ Planner    (decomposes task)
     ├──→ Researcher (gathers info, uses tools)
     ├──→ Writer     (synthesizes deliverable)
     └──→ Validator  (quality checks)
     
     Tools Available:
     🌤️ get_weather  🔍 search_web
     📊 calculate_metrics  📄 generate_report

     Config: max_rounds=10, max_stalls=3, max_resets=2
```

1. The orchestrator receives a complex task and **creates a plan** (task ledger).
2. It dynamically selects which agent should act next based on the current plan state.
3. Agents can use **tools** to interact with external systems (web search, calculations, reports).
4. The orchestrator tracks progress, detects stalls, and can reset if the workflow gets stuck.
5. Continues until the validator approves or safety limits are reached.

#### Key Code Construct

```python
workflow = MagenticBuilder().participants(
    planner=planner, researcher=researcher, 
    writer=writer, validator=validator
).on_event(on_event, mode=MagenticCallbackMode.STREAMING)
.with_standard_manager(
    chat_client=factory.chat_client,
    max_round_count=10,
    max_stall_count=3,
    max_reset_count=2
).build()
```

#### When to Use ✅

- Complex, open-ended problems with no predetermined solution path
- Tasks that benefit from a documented plan of approach before execution
- Workflows requiring tool integration (APIs, databases, calculations)
- Project management scenarios with planning, execution, and validation phases
- When you need human-auditable task ledgers

#### When to Avoid ❌

- The solution path is fixed and deterministic (use Sequential)
- Speed is more important than planning quality
- The task is simple enough for lighter patterns
- Frequent stalls are expected without clear resolution strategies

#### Tradeoffs

| Advantage | Disadvantage |
|-----------|-------------|
| Dynamic planning adapts to complex problems | Most complex pattern to implement and debug |
| Tool integration extends agent capabilities | Higher latency due to planning overhead |
| Task ledger provides transparency/auditability | Stall and reset mechanisms add unpredictability |
| Self-correcting through validation loops | Requires careful configuration of safety limits |

#### Real-World Scenarios

- **Employee wellness program** — Plan benefits → Research best practices → Design program → Validate compliance
- **Digital transformation** — Assess current state → Research technologies → Build roadmap → Validate feasibility
- **GDPR compliance framework** — Plan regulatory requirements → Research obligations → Draft policies → Validate coverage

---

### 6. Deep Research (ReAct) Pattern

**One sentence**: A multi-phase research pipeline that plans queries, gathers evidence through concurrent search, optionally runs code analysis, and produces a cited, reviewer-approved research brief.

#### How It Works

```
User Research Question
        ↓
┌─────────────┐
│   Planner   │ ← Uses probe tool to validate search queries
└─────────────┘
        ↓
┌─────────────┐
│ Researcher  │ ← Expands plan with additional search angles
└─────────────┘
        ↓
┌─────────────────────────────────────┐
│     Concurrent Evidence Gathering    │
│  Searcher₁ ‖ Searcher₂ ‖ Searcher₃  │  ← ConcurrentBuilder
└─────────────────────────────────────┘
        ↓ (optional, analyst/full mode)
┌─────────────┐
│   Analyst   │ ← Code Interpreter for data analysis
└─────────────┘
        ↓
┌─────────────┐
│   Writer    │ ← Produces cited research brief
└─────────────┘
        ↓ (optional, reviewer/full mode)
┌─────────────┐
│  Reviewer   │ ← Quality loop for gaps and accuracy
└─────────────┘
```

#### Execution Modes

| Mode | Pipeline | Best For |
|------|----------|----------|
| `baseline` | Planner → Researcher → Concurrent Search → Writer | Quick research briefs |
| `reviewer` | baseline + Reviewer quality loop | Higher-quality, vetted output |
| `analyst` | baseline + Code Interpreter analysis | Data-heavy research with computation |
| `private` | Uses private vector store instead of web search | Confidential/internal knowledge bases |
| `multimodal` | baseline + PDF ingestion via File Search | Research involving document analysis |
| `full` | All features enabled | Comprehensive research with all capabilities |

#### Role-Based Access Control

The pattern supports RBAC gating via `USER_ROLE`:

| Role | Available Tools |
|------|----------------|
| `viewer` | Bing search only |
| `doc-reader` | + File search |
| `analyst` | + Code interpreter |
| `admin` | All tools |

#### Key Code Constructs

```python
# Uses Azure AI Foundry Agents (persistent, not in-memory)
client = AgentsClient(endpoint=os.getenv("AZURE_AI_ENDPOINT"), ...)

# Planner uses probe tool to validate queries
probe_tool = probe_agent.as_tool(...)

# Concurrent evidence gathering
evidence_workflow = ConcurrentBuilder().participants(searchers).build()

# Mode-specific pipeline assembly
if mode in ("reviewer", "full"):
    # Add reviewer quality loop
if mode in ("analyst", "full"):
    # Add code interpreter
```

#### When to Use ✅

- Comprehensive research requiring multiple sources and citations
- Tasks needing both breadth (concurrent search) and depth (analysis)
- Scenarios requiring evidence-based, auditable conclusions
- When different research modes serve different security/access levels

#### When to Avoid ❌

- Simple questions with straightforward answers
- Speed is the top priority (this is the highest-latency pattern)
- No Azure AI Foundry infrastructure available
- Tasks that don't benefit from cited, multi-source evidence

#### Tradeoffs

| Advantage | Disadvantage |
|-----------|-------------|
| Most comprehensive output with citations | Highest latency and resource consumption |
| Flexible modes for different use cases | Largest configuration surface area |
| RBAC gating for enterprise scenarios | Requires Azure AI Foundry setup |
| Combines planning + search + analysis + review | Most complex to debug and maintain |
| Uses persistent Foundry agents (visible in portal) | Depends on multiple Azure services |

#### Real-World Scenarios

- **Market intelligence** — Multi-source competitive analysis with cited findings
- **Due diligence reports** — Evidence-gathered, reviewer-approved investment analysis
- **Technical research** — Code analysis + literature review for architecture decisions
- **Regulatory research** — Private document search + compliance gap analysis

---

## Decision Framework: Choosing the Right Pattern

Use this flowchart to select the right pattern for a given task:

```
Is the task a single, well-defined question?
├── YES → Can a single agent handle it?
│         ├── YES → No orchestration needed
│         └── NO  → Does it need multiple perspectives?
│                   ├── YES → CONCURRENT
│                   └── NO  → SEQUENTIAL
│
└── NO  → Does it require dynamic routing?
          ├── YES → HANDOFF
          └── NO  → Does it need iterative refinement?
                    ├── YES → How complex is it?
                    │         ├── Simple (2-3 rounds) → GROUP CHAT
                    │         └── Complex (planning + tools) → MAGENTIC
                    └── NO  → Does it need comprehensive research with citations?
                              ├── YES → DEEP RESEARCH
                              └── NO  → SEQUENTIAL or CONCURRENT
```

### Quick Selection Guide

| Your Scenario | Recommended Pattern | Why |
|---------------|-------------------|-----|
| Content pipeline (draft → edit → publish) | Sequential | Fixed stages, cumulative refinement |
| Evaluate a business decision from multiple angles | Concurrent | Independent perspectives, speed |
| Write and refine a deliverable through peer review | Group Chat | Iterative improvement via feedback |
| Route customer inquiries to the right department | Handoff | Dynamic specialist selection |
| Plan and execute a complex project end-to-end | Magentic | Goal-driven planning with tools |
| Produce a research brief with sources and citations | Deep Research | Multi-phase evidence gathering |
| Need the fastest possible result | Concurrent | Parallel execution |
| Need the highest quality result | Group Chat or Deep Research | Iteration / multi-source evidence |
| Need the most predictable result | Sequential | Deterministic pipeline |
| Need maximum flexibility | Magentic | Dynamic planning and tool use |

---

## Tradeoff Matrix

| Tradeoff Dimension | Sequential | Concurrent | Group Chat | Handoff | Magentic | Deep Research |
|--------------------|-----------|------------|------------|---------|----------|---------------|
| **Latency** | ⬛⬛⬛ Medium | ⬛ Low | ⬛⬛⬛⬛ High | ⬛⬛ Low-Med | ⬛⬛⬛⬛ High | ⬛⬛⬛⬛⬛ Highest |
| **Predictability** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ |
| **Output Quality** | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Implementation Complexity** | ⭐ Simple | ⭐ Simple | ⭐⭐⭐ Medium | ⭐⭐⭐ Medium | ⭐⭐⭐⭐ High | ⭐⭐⭐⭐⭐ Highest |
| **Debuggability** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ |
| **Scalability (add agents)** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| **Token Efficiency** | ⭐⭐ (cumulative context) | ⭐⭐⭐⭐ (isolated) | ⭐⭐ (full thread per round) | ⭐⭐⭐⭐ (2-step) | ⭐⭐ (many rounds) | ⭐ (multi-phase) |
| **Error Recovery** | ⭐ (no backtrack) | ⭐⭐⭐ (isolated failures) | ⭐⭐⭐⭐ (self-correcting) | ⭐⭐⭐ (fallback routing) | ⭐⭐⭐⭐ (stall/reset) | ⭐⭐⭐ (mode fallback) |

---

## Customer-Facing Scripts

### Opening: Setting the Stage

> "When we build AI agent systems, the most important architectural decision isn't which model to use — it's how the agents coordinate. Think of it like assembling a team: do you need them working in sequence like a relay race, in parallel like a SWAT team, or in a discussion like a boardroom meeting? That's what orchestration patterns solve."

---

### Script: Sequential Pattern

> **Elevator Pitch**: "Sequential is your assembly line. Each agent is a specialist at one station — the planner lays out the strategy, the researcher gathers evidence, the writer drafts the deliverable, and the reviewer checks quality. Each stage gets everything the previous stages produced, so context builds up naturally."
>
> **When to Recommend**: "Use this when your process has clear, ordered steps. Think content publishing pipelines, compliance workflows, or any process where Stage 2 genuinely needs Stage 1's output to do its job well."
>
> **Key Selling Point**: "It's the most predictable and auditable pattern. You can trace exactly what each agent contributed, in what order, and why. For regulated industries, that traceability is gold."
>
> **Honest Caveat**: "The tradeoff is speed — since agents run one at a time, total time is the sum of all stages. And if the planner makes a bad plan, that mistake propagates through every downstream agent. There's no built-in self-correction."

---

### Script: Concurrent Pattern

> **Elevator Pitch**: "Concurrent is your panel of experts. You give the same question to three specialists — say, a summarizer, a pros/cons analyst, and a risk assessor — and they all work on it at the same time. You get three independent perspectives in the time it takes for the slowest one to finish."
>
> **When to Recommend**: "Use this when you need multiple angles on the same problem and speed matters. Investment due diligence, crisis response planning, competitive analysis — anywhere a diversity of viewpoints improves the decision."
>
> **Key Selling Point**: "It's the fastest pattern. Since agents work in parallel with zero dependencies, your wall-clock time is the max, not the sum. Plus, if one agent fails, the others still deliver."
>
> **Honest Caveat**: "The agents don't collaborate — they don't even know each other exists. If the summarizer says 'go' and the risk assessor says 'stop', there's no built-in mechanism to resolve that. The human (or a downstream agent) needs to synthesize the perspectives."

---

### Script: Group Chat Pattern

> **Elevator Pitch**: "Group Chat is your editorial room. A writer drafts, a reviewer critiques, and a moderator decides whether it's good enough or needs another round. It's a maker-checker loop that keeps iterating until the output meets quality standards."
>
> **When to Recommend**: "Use this when quality matters more than speed, and the task benefits from back-and-forth refinement. Marketing copy, policy documents, research proposals — anything where a first draft is never the final draft."
>
> **Key Selling Point**: "It's self-correcting. Unlike Sequential where mistakes flow downstream, Group Chat catches issues and sends work back for revision. The full conversation is preserved, so you can see exactly how the output evolved through each round of feedback."
>
> **Honest Caveat**: "Iteration count is unpredictable — sometimes it converges in 2 rounds, sometimes it hits the max. The termination logic is heuristic (it looks for keywords like 'approved' or 'final'), so careful prompt engineering on the moderator is essential. We also recommend keeping it to 3 agents max — conversation management gets complex fast."

---

### Script: Handoff Pattern

> **Elevator Pitch**: "Handoff is your intelligent receptionist. A router agent reads the incoming request, decides which specialist should handle it — order tracking, returns, or general support — and transfers full ownership. It even provides a confidence score so you know how sure it is about the routing."
>
> **When to Recommend**: "Use this for customer service, IT help desks, healthcare triage — any scenario where requests arrive in unpredictable categories and need to reach the right specialist quickly."
>
> **Key Selling Point**: "The routing decision is structured and transparent. Every handoff includes a confidence score (0 to 1) and a written reasoning. That makes it auditable, debuggable, and easy to monitor in production. Plus, it has a graceful fallback — if JSON parsing fails, it falls back to text-based routing, and if no specialist matches, a default agent catches it."
>
> **Honest Caveat**: "Only one specialist handles each request — there's no multi-specialist collaboration. And the router is a single point of failure: if the routing prompt is poorly designed, requests end up with the wrong specialist. We recommend monitoring confidence scores in production and alerting on low-confidence routes."

---

### Script: Magentic Pattern

> **Elevator Pitch**: "Magentic is your project manager. It doesn't just execute — it plans first. The orchestrator creates a task ledger, delegates work to the right agents, tracks progress, and even provides tools like web search and report generation. If the workflow gets stuck, it can detect the stall and reset."
>
> **When to Recommend**: "Use this for complex, open-ended problems where you can't pre-define the solution path. Designing an employee wellness program, building a digital transformation roadmap, creating a compliance framework — tasks where planning is half the value."
>
> **Key Selling Point**: "The task ledger is the differentiator. Before any work happens, the system produces a documented plan that humans can review and approve. That's huge for enterprise customers who need governance and transparency. Plus, the tool integration means agents can pull real data — weather, metrics, web search — instead of just generating text."
>
> **Honest Caveat**: "It's the most complex pattern to configure and debug. You need to tune three safety parameters — max rounds, max stalls, and max resets — and getting those wrong can mean infinite loops or premature termination. The planning overhead also adds latency, so don't use it for simple tasks."

---

### Script: Deep Research (ReAct) Pattern

> **Elevator Pitch**: "Deep Research is your full research team in a box. It plans search queries, validates them with a probe tool, sends concurrent searchers to gather evidence, optionally runs code analysis, writes a cited report, and can even loop through a reviewer for quality. It comes in six modes — from a quick baseline to a full-featured pipeline with private data, PDF ingestion, and role-based access."
>
> **When to Recommend**: "Use this when the output needs to be evidence-based and citable. Market intelligence, technical research, regulatory analysis, due diligence — anywhere a 'trust me, the AI said so' answer isn't acceptable."
>
> **Key Selling Point**: "It's the only pattern that produces cited, source-backed research. The six modes let you tune the depth and feature set to the situation — a quick baseline for internal questions, full mode for board-level deliverables. And the RBAC gating means you can control who gets access to what tools based on their role."
>
> **Honest Caveat**: "It's the heaviest pattern — highest latency, highest token consumption, most Azure dependencies. It requires Azure AI Foundry infrastructure and proper endpoint configuration. This is the production research engine, not the quick-answer bot."

---

### Closing: Bringing It Together

> "The beauty of this sandbox is that you don't have to choose just one pattern forever. Many production systems combine patterns — a Handoff router on the front door that dispatches to a Sequential pipeline for structured work, a Concurrent fan-out for analysis, or a Deep Research engine for investigation. Start with the simplest pattern that solves your problem, and layer in complexity only when the use case demands it."

---

## Combining Patterns

Patterns are composable. Common combinations in production:

| Combination | How It Works | Example |
|-------------|-------------|---------|
| **Handoff → Sequential** | Route to the right department, then execute a stage-gated workflow | Customer request → Route to Returns → Process return sequentially |
| **Sequential with Concurrent stage** | Most stages are sequential, but one stage fans out in parallel | Plan → Research (3 parallel searchers) → Write → Review |
| **Group Chat → Sequential** | Iteratively refine a plan, then execute it through a pipeline | Debate strategy → Approve → Execute steps in order |
| **Handoff → Deep Research** | Route research requests to the full ReAct pipeline | Analyst query → Route → Deep Research with citations |

The Deep Research pattern already demonstrates internal composition: it uses `ConcurrentBuilder` inside a larger sequential pipeline for parallel evidence gathering.

---

## References

- [Microsoft Agent Framework (GitHub)](https://github.com/microsoft/agent-framework)
- [AI Agent Orchestration Design Patterns](https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns)
- [Semantic Kernel Agent Orchestration](https://learn.microsoft.com/en-us/semantic-kernel/frameworks/agent/agent-orchestration/)
- [Introducing Microsoft Agent Framework (Blog)](https://devblogs.microsoft.com/foundry/introducing-microsoft-agent-framework-the-open-source-engine-for-agentic-ai-apps/)
- [Multi-Agent Observability](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/azure-ai-foundry-advancing-opentelemetry-and-delivering-unified-multi-agent-obse/4456039)

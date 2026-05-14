# Agent Patterns Sandbox — Evaluation & Guides

> **Based on**: [akshata29/agents](https://github.com/akshata29/agents) — Original Microsoft Agent Framework patterns repository.

---

## Repository Structure

```mermaid
graph TD
    ROOT[["📁 patterns/"]] --> BE[["📁 backend/"]]
    ROOT --> FE[["📁 frontend/"]]
    ROOT --> DOCS[["📁 docs/"]]

    BE --> SEQ[sequential/]
    BE --> CONC[concurrent_pattern/]
    BE --> GC[group_chat/]
    BE --> HO[handoff/]
    BE --> MAG[magentic/]
    BE --> REACT[react/]
    BE --> BT{{"🆕 bank_teller/"}}
    BE --> PC{{"🆕 pattern_comparison.ipynb"}}
    BE --> COMMON[common/agents.py]

    BT --> KB[knowledge_base.py]
    BT --> EVAL[bank_teller_eval.ipynb]
    BT --> SEQ_R[sequential_retrieval.py]
    BT --> HO_R[handoff_retrieval.py]
    BT --> DS[eval_dataset.py]

    DOCS --> GUIDE{{"🆕 orchestration-patterns-guide.md"}}

    FE --> SRC[src/ — React + Vite + Tailwind]

    %% Accessible styling: shape + color + icon triple-encoding
    %% Using blue (#0969DA) for new items — passes WCAG AA on white
    %% Existing items use neutral gray — no color-only distinction
    style ROOT fill:#f6f8fa,stroke:#656d76,stroke-width:2px,color:#1f2328
    style BE fill:#f6f8fa,stroke:#656d76,stroke-width:2px,color:#1f2328
    style FE fill:#f6f8fa,stroke:#656d76,stroke-width:1px,color:#1f2328
    style DOCS fill:#f6f8fa,stroke:#656d76,stroke-width:1px,color:#1f2328
    style BT fill:#ddf4ff,stroke:#0969da,stroke-width:2px,color:#0550ae
    style PC fill:#ddf4ff,stroke:#0969da,stroke-width:2px,color:#0550ae
    style GUIDE fill:#ddf4ff,stroke:#0969da,stroke-width:2px,color:#0550ae
```

> **🆕 = Added in this fork** — distinguished by hexagonal shape, blue border, and 🆕 icon (triple-encoded for accessibility).

---

## What This Fork Adds

This fork extends the original repo with evaluation tooling, customer-facing documentation, and a hands-on comparison project.

### 🏦 Bank Teller Knowledge Retrieval Eval (`patterns/backend/bank_teller/`)

A standalone project comparing **Sequential vs Handoff** orchestration patterns for a bank teller knowledge retrieval use case with role-based access control (IC vs Manager).

- **Synthetic Banking KB** — 16 articles across 8 domains (accounts, wires, disputes, lending, compliance, financials, HR, overrides) with role-gated access
- **Two pattern implementations** — Sequential pipeline (Analyze → Retrieve → Generate → Format) and Handoff pipeline (Router → Role gate → Domain specialist)
- **50-case evaluation dataset** — Simple lookups, role-gated queries, multi-domain, compliance-sensitive, and edge cases
- **Jupyter evaluation notebook** — Full eval pipeline with metrics dashboard (latency, routing precision, role adherence), optional Azure AI Evaluation SDK judges, and a recommendation engine

### 📊 Pattern Comparison Notebook (`patterns/backend/pattern_comparison.ipynb`)

Compares 5 orchestration patterns against the same banking fraud scenario using Azure AI Foundry persistent agents. Includes latency, quality, and cost metrics.

### 📖 Orchestration Patterns Guide (`patterns/docs/orchestration-patterns-guide.md`)

Comprehensive customer-facing document covering all 6 patterns with:
- Architecture diagrams and tradeoff matrices
- Decision framework flowchart
- Customer talk-track scripts for each pattern
- Pattern composition guidance

### 🛠️ Developer Experience

- `.github/copilot-instructions.md` — Project conventions, endpoint guidance, eval best practices
- Application Insights tracing integration
- Azure endpoint documentation (which endpoint goes where)

---

*For setup instructions, pattern details, and architecture — see the [original repo](https://github.com/akshata29/agents/tree/main/patterns).*

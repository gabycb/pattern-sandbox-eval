"""
Handoff Retrieval Pattern for Bank Teller Knowledge Search

Pipeline: Router → Specialist (PolicyAgent | ComplianceAgent | LoanAgent | ManagerInsightsAgent)

The router classifies queries by domain and complexity, checks user role,
and delegates to the appropriate specialist. Role-gated routing prevents
IC users from accessing manager-only domains.
"""

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Optional

from pydantic import BaseModel, Field
from agent_framework import Message as ChatMessage

from bank_teller.knowledge_base import UserRole, Domain, retrieve, format_context
from bank_teller.agents import BankAgentFactory


class RoutingDecision(BaseModel):
    """Structured routing decision from the bank router agent."""
    specialist: str = Field(
        description="Target specialist",
        pattern="^(policy|compliance|lending|manager_insights)$",
    )
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(description="Brief routing explanation")
    requires_manager: bool = Field(default=False)


@dataclass
class HandoffResult:
    """Result from handoff retrieval pipeline."""
    query: str
    role: UserRole
    answer: str
    context_used: str
    latency_seconds: float
    articles_found: int
    routing_decision: Optional[dict] = None
    specialist_used: str = ""
    was_role_blocked: bool = False


# Map specialist names to KB domains for targeted retrieval
SPECIALIST_DOMAINS = {
    "policy": [Domain.ACCOUNTS, Domain.WIRE_TRANSFERS, Domain.DISPUTES],
    "compliance": [Domain.COMPLIANCE],
    "lending": [Domain.LENDING],
    "manager_insights": [Domain.FINANCIALS, Domain.HR, Domain.OVERRIDES],
}


def _parse_routing_decision(text: str) -> RoutingDecision:
    """Parse routing decision from agent response, with fallback."""
    text = text.strip()

    # Try direct JSON parse
    try:
        # Extract JSON from markdown code blocks if present
        if "```" in text:
            json_start = text.find("{")
            json_end = text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                text = text[json_start:json_end]
        return RoutingDecision.model_validate_json(text)
    except Exception:
        pass

    # Fallback: look for JSON object in the text
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        return RoutingDecision.model_validate_json(text[start:end])
    except Exception:
        pass

    # Last resort: keyword-based routing
    text_lower = text.lower()
    if any(kw in text_lower for kw in ["compliance", "bsa", "aml", "ctr", "sar"]):
        specialist = "compliance"
    elif any(kw in text_lower for kw in ["loan", "mortgage", "lending", "heloc", "credit"]):
        specialist = "lending"
    elif any(kw in text_lower for kw in ["p&l", "revenue", "staffing", "override", "headcount"]):
        specialist = "manager_insights"
    else:
        specialist = "policy"

    return RoutingDecision(
        specialist=specialist,
        confidence=0.5,
        reasoning="Fallback keyword-based routing",
        requires_manager="manager" in text_lower,
    )


async def run_handoff_retrieval(
    query: str,
    role: UserRole = UserRole.IC,
    activity_callback=None,
) -> HandoffResult:
    """
    Execute the handoff retrieval pipeline.

    Flow:
    1. Router classifies query → specialist + role check
    2. Role gate: block IC users from manager-only domains
    3. Targeted KB retrieval using specialist's domain
    4. Specialist agent generates answer
    """
    start_time = time.time()
    factory = BankAgentFactory()

    # Step 1: Route the query
    router = factory.create_router()

    routing_prompt = [
        ChatMessage(role="user", contents=[
            f"User Role: {role.value.upper()}\n"
            f"Query: {query}\n\n"
            f"Route this query to the appropriate specialist."
        ])
    ]

    if activity_callback:
        await activity_callback("🔀 Router analyzing query...")

    router_response = await router.run(routing_prompt)
    routing_text = ""
    if router_response.messages:
        routing_text = router_response.messages[-1].text

    decision = _parse_routing_decision(routing_text)

    if activity_callback:
        await activity_callback(
            f"🎯 Routed to '{decision.specialist}' (confidence: {decision.confidence:.0%}): {decision.reasoning}"
        )

    # Step 2: Role gate
    was_blocked = False
    if decision.specialist == "manager_insights" and role == UserRole.IC:
        was_blocked = True
        if activity_callback:
            await activity_callback("🚫 Access denied: manager-only domain requested by IC user")

        elapsed = time.time() - start_time
        return HandoffResult(
            query=query,
            role=role,
            answer=(
                "I'm sorry, but that information is only available to managers. "
                "The data you're requesting (branch financials, staffing, or override authorities) "
                "requires manager-level access. Please ask your branch manager for assistance."
            ),
            context_used="",
            latency_seconds=elapsed,
            articles_found=0,
            routing_decision=decision.model_dump(),
            specialist_used=decision.specialist,
            was_role_blocked=True,
        )

    # Step 3: Targeted KB retrieval using specialist's domains
    articles = retrieve(query, role=role, top_k=3)
    context = format_context(articles)

    if activity_callback:
        await activity_callback(f"📚 Retrieved {len(articles)} articles for {decision.specialist}")

    # Step 4: Dispatch to specialist agent
    specialist_map = {
        "policy": factory.create_policy_agent,
        "compliance": factory.create_compliance_agent,
        "lending": factory.create_loan_agent,
        "manager_insights": factory.create_manager_insights_agent,
    }

    create_specialist = specialist_map.get(decision.specialist, factory.create_policy_agent)
    specialist = create_specialist()

    specialist_prompt = [
        ChatMessage(role="user", contents=[
            f"User Role: {role.value.upper()}\n"
            f"Query: {query}\n\n"
            f"--- Retrieved Knowledge Base Context ---\n{context}\n"
            f"--- End Context ---\n\n"
            f"Please answer the query using ONLY the provided context. "
            f"Format your response clearly for a bank teller who may be on the phone."
        ])
    ]

    if activity_callback:
        await activity_callback(f"💬 {decision.specialist.title()} specialist generating answer...")

    specialist_response = await specialist.run(specialist_prompt)
    answer = ""
    if specialist_response.messages:
        answer = specialist_response.messages[-1].text

    elapsed = time.time() - start_time

    if activity_callback:
        await activity_callback(f"✅ Handoff pipeline complete in {elapsed:.1f}s (specialist: {decision.specialist})")

    return HandoffResult(
        query=query,
        role=role,
        answer=answer,
        context_used=context,
        latency_seconds=elapsed,
        articles_found=len(articles),
        routing_decision=decision.model_dump(),
        specialist_used=decision.specialist,
        was_role_blocked=was_blocked,
    )

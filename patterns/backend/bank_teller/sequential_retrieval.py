"""
Sequential Retrieval Pattern for Bank Teller Knowledge Search

Pipeline: QueryAnalyzer → KBRetriever → ResponseGenerator → QualityChecker

All queries go through the same pipeline regardless of complexity or domain.
Role-based filtering happens at the retrieval layer (KB lookup).
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Optional

from agent_framework import Message as ChatMessage
from agent_framework.orchestrations import SequentialBuilder

from bank_teller.knowledge_base import UserRole, retrieve, format_context
from bank_teller.agents import BankAgentFactory


def _is_output_event(event: object) -> bool:
    return getattr(event, "type", None) == "output"


@dataclass
class SequentialResult:
    """Result from sequential retrieval pipeline."""
    query: str
    role: UserRole
    answer: str
    context_used: str
    latency_seconds: float
    articles_found: int


async def run_sequential_retrieval(
    query: str,
    role: UserRole = UserRole.IC,
    activity_callback=None,
) -> SequentialResult:
    """
    Execute the sequential retrieval pipeline.

    Flow:
    1. QueryAnalyzer — classifies the query
    2. KBRetriever (non-agent) — fetches relevant KB articles filtered by role
    3. PolicyAgent — generates answer using retrieved context
    4. ResponseFormatter — quality checks and formats the answer
    """
    start_time = time.time()
    factory = BankAgentFactory()

    # Step 1: Retrieve relevant KB articles (role-filtered)
    articles = retrieve(query, role=role, top_k=3)
    context = format_context(articles)

    if activity_callback:
        await activity_callback(f"📚 Retrieved {len(articles)} KB articles for role={role.value}")

    # Step 2: Build sequential pipeline with agents
    analyzer = factory.create_query_analyzer()
    # Pick the right domain agent based on a simple heuristic
    # (in sequential mode, we use the policy agent as a general-purpose answerer)
    responder = factory.create_policy_agent()
    formatter = factory.create_response_formatter()

    workflow = SequentialBuilder(participants=[
        analyzer,
        responder,
        formatter,
    ]).build()

    # Compose the prompt with retrieved context
    augmented_query = (
        f"User Role: {role.value.upper()}\n"
        f"Query: {query}\n\n"
        f"--- Retrieved Knowledge Base Context ---\n{context}\n"
        f"--- End Context ---\n\n"
        f"Please answer the query using ONLY the provided context."
    )

    if activity_callback:
        await activity_callback("🔄 Running sequential pipeline: Analyzer → Responder → Formatter")

    # Execute the sequential workflow (non-streaming for simplicity)
    result = await workflow.run(augmented_query, stream=False)

    # Extract the final answer from workflow outputs
    final_answer = ""
    outputs = result.get_outputs()
    if outputs:
        # get_outputs() returns output events; get the last message text
        last_output = outputs[-1] if isinstance(outputs, list) else outputs
        if hasattr(last_output, "data"):
            data = last_output.data
            if hasattr(data, "text"):
                final_answer = data.text
            elif isinstance(data, list):
                for msg in reversed(data):
                    if hasattr(msg, "text") and msg.text and getattr(msg, "role", "") != "user":
                        final_answer = msg.text
                        break
            elif isinstance(data, str):
                final_answer = data
        elif hasattr(last_output, "text"):
            final_answer = last_output.text

    # Fallback: iterate result directly (it's list-like)
    if not final_answer and result:
        for event in reversed(result):
            if hasattr(event, "data"):
                data = event.data
                if hasattr(data, "text") and data.text:
                    final_answer = data.text
                    break

    elapsed = time.time() - start_time

    if activity_callback:
        await activity_callback(f"✅ Sequential pipeline complete in {elapsed:.1f}s")

    return SequentialResult(
        query=query,
        role=role,
        answer=final_answer,
        context_used=context,
        latency_seconds=elapsed,
        articles_found=len(articles),
    )

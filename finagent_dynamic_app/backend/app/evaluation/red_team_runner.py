"""Red team evaluation runner for financial agents.

Adapts Azure AI Evaluation sample to run against existing
Microsoft Agent Framework agents provisioned by this project.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Awaitable, Callable, Iterable, List

from azure.identity import AzureCliCredential
from dotenv import load_dotenv

from app.infra.settings import Settings
from app.maf.agent_factory import MAFAgentFactory

# Load environment variables early so Settings can resolve them.
load_dotenv()

if sys.platform.startswith("win") and hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    # Ensure aiodns-based credentials work on Windows where Proactor loop is default.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def _parse_enum_values(
    raw_values: Iterable[str],
    enum_members: Iterable[Any],
    *,
    descriptor: str,
    allow_empty: bool = False,
) -> List[Any]:
    """Convert CLI strings to matching enum members."""
    members = {member.name.lower(): member for member in enum_members}
    resolved: List[Any] = []
    for value in raw_values:
        key = value.strip().lower()
        if not key:
            continue
        if key not in members:
            raise argparse.ArgumentTypeError(
                f"Unknown value '{value}' for {descriptor}; choose from {', '.join(members)}"
            )
        resolved.append(members[key])
    if not resolved and not allow_empty:
        raise argparse.ArgumentTypeError(f"At least one value required for {descriptor}")
    return resolved


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Azure AI red team evaluation against a financial agent",
    )
    parser.add_argument(
        "agent",
        metavar="AGENT",
        help="Agent type registered in MAFAgentFactory (e.g. planner, summarizer)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="File path for the red team scorecard JSON output (omit to skip local file)",
    )
    parser.add_argument(
        "--risk-categories",
        nargs="*",
        default=["violence", "hateunfairness", "sexual", "selfharm"],
        help="Risk categories to target (names from azure.ai.evaluation.red_team.RiskCategory)",
    )
    parser.add_argument(
        "--strategies",
        nargs="*",
        default=[
            "easy",
            "moderate",
            "characterspace",
            "rot13",
            "unicodeconfusable",
            "charswap",
            "morse",
            "leetspeak",
            "url",
            "binary",
        ],
        help="Attack strategies to apply (names from AttackStrategy)",
    )
    parser.add_argument(
        "--objectives",
        type=int,
        default=5,
        help="Number of attack objectives per risk category",
    )
    parser.add_argument(
        "--scan-name",
        default=None,
        help="Custom name for the scan shown in Azure AI Foundry",
    )
    return parser


async def _run_agent(
    agent_callable: Callable[[str], Awaitable[Any]],
    prompt: str,
) -> dict[str, List[Any]]:
    """Invoke the agent and coerce the response into Red Team format."""
    try:
        response = await agent_callable(prompt)
    except Exception as exc:  # pragma: no cover - evaluation safety
        return {"messages": [{"role": "assistant", "content": f"Agent execution failed: {exc}"}]}

    if isinstance(response, str):
        content = response
    else:
        # ChatAgent returns an object with `.text`; fall back to repr otherwise.
        content = getattr(response, "text", None) or repr(response)

    return {"messages": [{"role": "assistant", "content": content}]}


async def main() -> None:
    args = _build_parser().parse_args()

    try:  # Import lazily so the module remains optional.
        from azure.ai.evaluation.red_team import AttackStrategy, RedTeam, RiskCategory  # type: ignore[attr-defined]
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError(
            "azure-ai-evaluation package is required for red team evaluation. "
            "Install it with 'pip install azure-ai-evaluation'."
        ) from exc

    risk_categories = _parse_enum_values(
        args.risk_categories,
        RiskCategory,
        descriptor="RiskCategory",
    )
    attack_strategies = _parse_enum_values(
        args.strategies,
        AttackStrategy,
        descriptor="AttackStrategy",
    )

    settings = Settings()
    credential = AzureCliCredential()

    factory = MAFAgentFactory(settings)
    await factory.prepare()

    chat_agent = factory.create_chat_agent(agent_type=args.agent)

    async def agent_callback(query: str) -> dict[str, List[Any]]:
        return await _run_agent(chat_agent.run, query)

    red_team = RedTeam(
        azure_ai_project=settings.AZURE_AI_PROJECT_ENDPOINT,
        credential=credential,
        risk_categories=risk_categories,
        num_objectives=args.objectives,
    )

    attack_name = args.scan_name or f"{args.agent}-financial-redteam"

    print("Starting red team evaluation...")
    print(f"Agent: {args.agent}")
    print(f"Risk categories: {[cat.name for cat in risk_categories]}")
    print(f"Strategies: {[strategy.name for strategy in attack_strategies]}")
    print(f"Objectives per category: {args.objectives}\n")

    try:
        scan_kwargs = dict(
            target=agent_callback,
            scan_name=attack_name,
            attack_strategies=attack_strategies,
        )
        if args.output:
            scan_kwargs["output_path"] = str(args.output)

        results = await red_team.scan(**scan_kwargs)
    finally:
        await factory.close()

    print("Red team evaluation complete.\n")
    print(json.dumps(results.to_scorecard(), indent=2))


if __name__ == "__main__":
    asyncio.run(main())

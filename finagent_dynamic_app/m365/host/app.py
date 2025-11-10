"""Microsoft 365 Agents SDK host that exposes the autonomous research experience."""

from __future__ import annotations

import asyncio
import inspect
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

from aiohttp.web import Application, Request, Response, run_app
from dotenv import load_dotenv
from microsoft_agents.hosting.aiohttp import (
    CloudAdapter,
    jwt_authorization_middleware,
    start_agent_process,
)
from microsoft_agents.hosting.core import (
    AgentApplication,
    AgentAuthConfiguration,
    MemoryStorage,
    TurnContext,
    TurnState,
)

BACKEND_ROOT = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.infra.settings import Settings  # type: ignore[import]
from m365.host.adapters import ActivityEmitter, PlannerRunnerAdapter

load_dotenv()
load_dotenv(".env.m365", override=True)

LOGGER = logging.getLogger("m365.host")
SETTINGS = Settings()
FEATURE_ENABLED = bool(os.getenv("ENABLE_M365_AGENT", str(SETTINGS.ENABLE_M365_AGENT)).lower() in {"1", "true", "yes"})

ADAPTER = CloudAdapter()
AGENT_APP: AgentApplication[TurnState] = AgentApplication[TurnState](
    storage=MemoryStorage(),
    adapter=ADAPTER,
)

_adapter_instance: Optional[PlannerRunnerAdapter] = None
_adapter_lock = asyncio.Lock()


class TeamsActivityEmitter(ActivityEmitter):
    """Activity emitter that forwards events back through the adapter."""

    def __init__(self, context: TurnContext) -> None:
        self._context = context

    async def send(self, name: str, payload: Dict[str, Any]) -> None:
        activity = {
            "type": "event",
            "name": name,
            "value": payload,
        }
        await self._context.send_activity(activity)


async def _resolve_adapter() -> PlannerRunnerAdapter:
    global _adapter_instance
    if _adapter_instance is not None:
        return _adapter_instance

    async with _adapter_lock:
        if _adapter_instance is None:
            LOGGER.info("Creating PlannerRunnerAdapter for Microsoft 365 host")
            _adapter_instance = PlannerRunnerAdapter(settings=Settings())
        return _adapter_instance


async def _run_research(context: TurnContext, _: TurnState) -> None:
    if not FEATURE_ENABLED:
        await context.send_activity("Microsoft 365 agent integration is disabled.")
        return

    payload = _extract_payload(context)
    decision = (payload.get("decision") or "").lower()
    user_id = _extract_user(context)
    emitter = TeamsActivityEmitter(context)
    adapter = await _resolve_adapter()

    if decision == "continue":
        plan_id = payload.get("planId")
        session_id = payload.get("sessionId")
        if not plan_id or not session_id:
            await context.send_activity("Missing planId or sessionId for continuation.")
            return

        try:
            await adapter.run_plan(
                plan_id=plan_id,
                session_id=session_id,
                user_id=user_id,
                emitter=emitter,
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            LOGGER.exception("Failed to execute plan", plan_id=plan_id, session_id=session_id)
            await _emit_failure(context, plan_id, session_id, str(exc))
        return

    if decision == "modify":
        await context.send_activity(
            {
                "type": "message",
                "text": "Plan modification is best handled in the web experience for now.",
            }
        )
        return

    objective = payload.get("objective") or (context.activity.text or "").strip()
    if not objective:
        await context.send_activity("Provide an objective to start the research task.")
        return

    try:
        plan = await adapter.create_plan(objective=objective, user_id=user_id, emitter=emitter)
    except Exception as exc:  # pragma: no cover - defensive logging
        LOGGER.exception("Failed to create plan", objective=objective[:100])
        await _emit_failure(context, None, None, str(exc))
        return

    await _send_confirm_step(context, plan)


def _register_handlers() -> None:
    if hasattr(AGENT_APP, "intent"):
        AGENT_APP.intent("runResearch")(_run_research)  # type: ignore[attr-defined]
    else:
        AGENT_APP.activity("invoke")(_run_research)


async def _emit_failure(context: TurnContext, plan_id: Optional[str], session_id: Optional[str], error: str) -> None:
    payload = {
        "error": error,
    }
    if plan_id:
        payload["planId"] = plan_id
    if session_id:
        payload["sessionId"] = session_id

    await context.send_activity(
        {
            "type": "event",
            "name": "exec.failed",
            "value": payload,
        }
    )
    await context.send_activity(
        {
            "type": "message",
            "text": f"Execution failed: {error}",
        }
    )


async def _send_confirm_step(context: TurnContext, plan) -> None:
    payload = {
        "planId": plan.id,
        "sessionId": plan.session_id,
        "objective": plan.initial_goal,
        "totalSteps": len(plan.steps),
    }
    await context.send_activity(
        {
            "type": "event",
            "name": "plan.confirm",
            "value": payload,
        }
    )
    await context.send_activity(
        {
            "type": "message",
            "text": "Plan ready. Modify or continue?",
            "value": payload,
        }
    )


def _extract_payload(context: TurnContext) -> Dict[str, Any]:
    value = context.activity.value or {}
    if isinstance(value, dict):
        return value
    return {}


def _extract_user(context: TurnContext) -> str:
    if context.activity.from_property and context.activity.from_property.id:
        return context.activity.from_property.id
    return "m365-user"


def _build_auth_configuration(settings: Settings) -> Optional[AgentAuthConfiguration]:
    client_id = settings.m365_bot_id or settings.m365_client_id
    client_secret = settings.m365_bot_password or settings.m365_client_secret
    tenant_id = settings.m365_tenant_id

    if not client_id or not client_secret:
        return None

    kwargs: Dict[str, Any] = {}
    signature = inspect.signature(AgentAuthConfiguration)
    if "client_id" in signature.parameters:
        kwargs["client_id"] = client_id
    if "client_secret" in signature.parameters:
        kwargs["client_secret"] = client_secret
    if "tenant_id" in signature.parameters and tenant_id:
        kwargs["tenant_id"] = tenant_id
    if not kwargs:
        return None
    return AgentAuthConfiguration(**kwargs)


def _build_web_app(agent_application: AgentApplication[TurnState], auth_configuration: Optional[AgentAuthConfiguration]) -> Application:
    async def entry_point(req: Request) -> Response:
        agent: AgentApplication[TurnState] = req.app["agent_app"]
        adapter: CloudAdapter = req.app["adapter"]
        config: Optional[AgentAuthConfiguration] = req.app.get("agent_configuration")
        try:
            return await start_agent_process(req, agent, adapter, config)
        except TypeError:  # Older SDK versions expose a 3-arg signature
            return await start_agent_process(req, agent, adapter)

    app = Application(middlewares=[jwt_authorization_middleware])
    app.router.add_post("/api/messages", entry_point)
    app.router.add_get("/api/messages", lambda _: Response(status=200))
    app["agent_app"] = agent_application
    app["adapter"] = agent_application.adapter
    app["agent_configuration"] = auth_configuration

    async def _cleanup(_: Application) -> None:
        if _adapter_instance is not None:
            await _adapter_instance.shutdown()

    app.on_cleanup.append(_cleanup)
    return app


def _resolve_binding(settings: Settings) -> Tuple[str, int]:
    base_url = settings.m365_host_base_url
    if base_url:
        parsed = urlparse(base_url)
        host = parsed.hostname or "0.0.0.0"
        port = parsed.port or 3978
        return host, port

    host = os.getenv("M365_HOST_BIND_ADDRESS", "0.0.0.0")
    port = int(os.getenv("M365_HOST_PORT", "3978"))
    return host, port


def main() -> None:
    logging.basicConfig(level=logging.INFO)

    if not FEATURE_ENABLED:
        LOGGER.warning("ENABLE_M365_AGENT is disabled; skipping Microsoft 365 host startup.")
        return

    auth_config = _build_auth_configuration(SETTINGS)
    _register_handlers()

    host, port = _resolve_binding(SETTINGS)
    LOGGER.info("Starting Microsoft 365 Agents host", extra={"host": host, "port": port})

    web_app = _build_web_app(AGENT_APP, auth_config)
    run_app(web_app, host=host, port=port)


if __name__ == "__main__":
    main()

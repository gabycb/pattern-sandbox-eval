"""Chat autorun API router."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from ..auth.auth_utils import get_authenticated_user_details
from ..infra.settings import Settings
from ..models.chat_models import (
    ChatCancelRequest,
    ChatConfigResponse,
    ChatConfirmRequest,
    ChatConfirmResponse,
    ChatObjectiveRequest,
    ChatObjectiveResponse,
    ChatStatusResponse,
)
from ..models.task_models import InputTask, PlanStatus
from ..services.chat_pubsub import ChatPubSubPublisher
from ..services.chat_runner import ChatRunManager
from ..services.task_orchestrator import TaskOrchestrator
from .orchestration import get_task_orchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"], include_in_schema=False)

_chat_publisher: Optional[ChatPubSubPublisher] = None
_chat_run_manager = ChatRunManager()

@router.get("/config", response_model=ChatConfigResponse)
async def get_chat_config() -> ChatConfigResponse:
    """Expose server-side chat feature configuration."""

    settings = Settings()
    return ChatConfigResponse(enabled=settings.enable_chat_autorun)


def _ensure_feature_enabled(settings: Settings) -> None:
    if not settings.enable_chat_autorun:
        raise HTTPException(status_code=404, detail="Chat autorun is disabled")


def _get_chat_publisher(settings: Settings) -> ChatPubSubPublisher:
    global _chat_publisher
    print(f"\n=== _get_chat_publisher called ===")
    print(f"Existing publisher: {_chat_publisher is not None}")
    logger.info(f"_get_chat_publisher called: existing_publisher={_chat_publisher is not None}")
    if _chat_publisher is None:
        print("Creating new ChatPubSubPublisher...")
        logger.info("Creating new ChatPubSubPublisher instance")
        _chat_publisher = ChatPubSubPublisher(settings)
        print(f"Publisher created, enabled: {_chat_publisher.is_enabled}")
        logger.info(f"ChatPubSubPublisher created: enabled={_chat_publisher.is_enabled}")
    return _chat_publisher


@router.post("/objective", response_model=ChatObjectiveResponse)
async def create_chat_plan(
    payload: ChatObjectiveRequest,
    request: Request,
    orchestrator: TaskOrchestrator = Depends(get_task_orchestrator),
):
    """Create a new plan for the chat autorun experience."""
    settings = Settings()
    _ensure_feature_enabled(settings)

    user_details = get_authenticated_user_details(request_headers=request.headers)
    user_id = user_details.get("user_principal_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User authentication required")

    logger.info("Chat objective received", user_id=user_id, objective_preview=payload.objective[:120])

    input_task = InputTask(
        description=payload.objective,
        user_id=user_id,
        ticker=payload.ticker,
        scope=payload.scope,
    )

    plan_with_steps = await orchestrator.create_plan_from_objective(input_task)

    publisher = _get_chat_publisher(settings)
    access = await publisher.get_client_access(user_id=user_id, task_id=plan_with_steps.id)

    response = ChatObjectiveResponse(
        task_id=plan_with_steps.id,
        session_id=plan_with_steps.session_id,
        plan=plan_with_steps,
        web_pubsub_url=access.get("url") if access else None,
        web_pubsub_group=access.get("group") if access else None,
    )

    logger.info(
        "Chat plan created",
        task_id=plan_with_steps.id,
        session_id=plan_with_steps.session_id,
        steps=len(plan_with_steps.steps),
    )

    return response


@router.post("/confirm", response_model=ChatConfirmResponse)
async def confirm_chat_plan(
    payload: ChatConfirmRequest,
    request: Request,
    orchestrator: TaskOrchestrator = Depends(get_task_orchestrator),
):
    """Confirm or modify a generated plan prior to autonomous execution."""
    settings = Settings()
    _ensure_feature_enabled(settings)

    plan = await orchestrator.cosmos.get_plan(payload.task_id, payload.session_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    session_id = plan.session_id

    if payload.steps:
        for patch in payload.steps:
            step = await orchestrator.cosmos.get_step(patch.id, session_id)
            if not step or step.plan_id != payload.task_id:
                raise HTTPException(status_code=404, detail=f"Step not found: {patch.id}")
            if patch.action is not None:
                step.action = patch.action
            if patch.human_feedback is not None:
                step.human_feedback = patch.human_feedback
            await orchestrator.cosmos.update_step(step)

    plan_with_steps = await orchestrator.get_plan_with_steps(payload.task_id, session_id)
    if not plan_with_steps:
        raise HTTPException(status_code=404, detail="Unable to load plan state")

    if payload.action == "modify":
        return ChatConfirmResponse(task_id=plan_with_steps.id, session_id=session_id, plan=plan_with_steps)

    user_details = get_authenticated_user_details(request_headers=request.headers)
    user_id = user_details.get("user_principal_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User authentication required")

    publisher = _get_chat_publisher(settings)
    print(f"\n=== confirm_chat_plan ===")
    print(f"Publisher enabled: {publisher.is_enabled}")
    print(f"Task ID: {plan_with_steps.id}")
    print(f"Session ID: {session_id}")
    print(f"Starting run...")
    
    logger.info(
        f"confirm_chat_plan: Starting run with publisher (enabled={publisher.is_enabled}), "
        f"task_id={plan_with_steps.id}, session_id={session_id}"
    )
    await _chat_run_manager.start_run(
        task_id=plan_with_steps.id,
        session_id=session_id,
        user_id=user_id,
        orchestrator=orchestrator,
        publisher=publisher,
    )

    return ChatConfirmResponse(task_id=plan_with_steps.id, session_id=session_id, plan=plan_with_steps)


@router.post("/cancel")
async def cancel_chat_run(
    payload: ChatCancelRequest,
    orchestrator: TaskOrchestrator = Depends(get_task_orchestrator),
):
    settings = Settings()
    _ensure_feature_enabled(settings)

    plan = await orchestrator.cosmos.get_plan(payload.task_id, payload.session_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    cancelled = await _chat_run_manager.cancel_run(task_id=payload.task_id)
    if cancelled:
        return {"message": "Cancellation requested"}

    plan.overall_status = PlanStatus.CANCELLED
    await orchestrator.cosmos.update_plan(plan)
    return {"message": "No active run to cancel, plan marked cancelled"}


@router.get("/status", response_model=ChatStatusResponse)
async def get_chat_status(
    taskId: str,
    sessionId: Optional[str] = None,
    orchestrator: TaskOrchestrator = Depends(get_task_orchestrator),
):
    settings = Settings()
    _ensure_feature_enabled(settings)

    session_id = sessionId
    if not session_id:
        plan = await orchestrator.cosmos.get_plan(taskId)
        if not plan:
            raise HTTPException(status_code=404, detail=f"Plan {taskId} not found")
        session_id = plan.session_id

    plan_with_steps = await orchestrator.get_plan_with_steps(taskId, session_id)
    if not plan_with_steps:
        raise HTTPException(status_code=404, detail=f"Plan {taskId} not found")

    messages = await orchestrator.cosmos.get_messages_by_plan(taskId)

    return ChatStatusResponse(
        task_id=plan_with_steps.id,
        session_id=plan_with_steps.session_id,
        plan=plan_with_steps,
        messages=messages,
    )

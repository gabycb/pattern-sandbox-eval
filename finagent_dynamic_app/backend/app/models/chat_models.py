"""Pydantic models for the autonomous chat execution API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from .task_models import AgentMessage, PlanWithSteps


class ChatObjectiveRequest(BaseModel):
    """Request payload for generating a plan from a chat objective."""

    objective: str = Field(..., min_length=5, description="Research objective provided by the user")
    ticker: Optional[str] = Field(default=None, description="Optional ticker symbol for additional context")
    scope: Optional[List[str]] = Field(default=None, description="Optional analysis scope hints")


class ChatObjectiveResponse(BaseModel):
    """Response payload after creating a plan for the chat flow."""

    task_id: str
    session_id: str
    plan: PlanWithSteps
    web_pubsub_url: Optional[str] = None
    web_pubsub_group: Optional[str] = None


class ChatConfigResponse(BaseModel):
    """Configuration response describing chat feature availability."""

    enabled: bool


class StepPatch(BaseModel):
    """Permitted step mutations prior to autonomous execution."""

    id: str
    action: Optional[str] = Field(default=None, description="Updated step objective/action text")
    human_feedback: Optional[str] = Field(default=None, description="Optional inline notes persisted on the step")


class ChatConfirmRequest(BaseModel):
    """Request payload for confirming or modifying a generated plan."""

    task_id: str
    session_id: Optional[str] = None
    action: Literal["continue", "modify"] = "continue"
    steps: Optional[List[StepPatch]] = Field(default=None, description="Step edits allowed prior to execution")


class ChatConfirmResponse(BaseModel):
    """Response payload after confirming or modifying a plan."""

    task_id: str
    session_id: str
    plan: PlanWithSteps


class ChatCancelRequest(BaseModel):
    """Request payload to cancel an in-flight autonomous execution."""

    task_id: str
    session_id: Optional[str] = None


class ChatStatusResponse(BaseModel):
    """Polling response describing the current plan and timeline."""

    task_id: str
    session_id: str
    plan: PlanWithSteps
    messages: List[AgentMessage]
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ChatEventPayload(BaseModel):
    """Common structure for Web PubSub payloads."""

    type: Literal[
        "plan_created",
        "plan_updated",
        "step_started",
        "step_completed",
        "step_failed",
        "plan_status",
        "message",
        "run_finished",
        "run_cancelled",
        "run_failed",
    ]
    task_id: str
    session_id: str
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ChatRunSnapshot(BaseModel):
    """Internal snapshot used for status aggregation."""

    plan: PlanWithSteps
    messages: List[AgentMessage]

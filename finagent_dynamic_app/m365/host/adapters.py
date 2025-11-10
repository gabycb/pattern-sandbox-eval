"""Adapters bridging the existing planner/runner services to the Microsoft 365 Agents host."""

from __future__ import annotations

import asyncio
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Protocol

BACKEND_ROOT = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.infra.settings import Settings  # type: ignore[import]
from app.models.task_models import (  # type: ignore[import]
    ActionResponse,
    HumanFeedback,
    InputTask,
    PlanWithSteps,
    Step,
    StepStatus,
)
from app.services.task_orchestrator import TaskOrchestrator  # type: ignore[import]

logger = logging.getLogger(__name__)


class ActivityEmitter(Protocol):
    """Minimal protocol for sending activity payloads back to the channel."""

    async def send(self, name: str, payload: Dict[str, Any]) -> None:
        """Send an activity with the supplied name and payload."""


@dataclass
class PlanRunContext:
    """Light-weight envelope passed to the sequential run pipeline."""

    plan: PlanWithSteps
    user_id: str


class PlannerRunnerAdapter:
    """Thin wrapper around TaskOrchestrator for the Microsoft 365 host."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        orchestrator: Optional[TaskOrchestrator] = None,
    ) -> None:
        self._settings = settings or Settings()
        self._orchestrator = orchestrator
        self._initialize_lock = asyncio.Lock()
        self._initialized = False

    @property
    def orchestrator(self) -> TaskOrchestrator:
        if self._orchestrator is None:
            self._orchestrator = TaskOrchestrator(self._settings)
        return self._orchestrator

    async def initialize(self) -> None:
        """Ensure the underlying TaskOrchestrator is ready for use."""
        if self._initialized:
            return

        async with self._initialize_lock:
            if self._initialized:
                return

            logger.info("Initializing PlannerRunnerAdapter")
            await self.orchestrator.initialize()
            self._initialized = True

    async def shutdown(self) -> None:
        """Dispose orchestrator resources when the host stops."""
        if not self._initialized:
            return

        logger.info("Shutting down PlannerRunnerAdapter")
        await self.orchestrator.shutdown()
        self._initialized = False

    async def create_plan(
        self,
        *,
        objective: str,
        user_id: str,
        emitter: ActivityEmitter,
    ) -> PlanWithSteps:
        """Create a plan using the existing planner flow and emit plan.created."""
        await self.initialize()

        task = InputTask(description=objective, user_id=user_id)
        plan = await self.orchestrator.create_plan_from_objective(task)

        logger.info(
            "Plan created for Microsoft 365 request",
            plan_id=plan.id,
            session_id=plan.session_id,
            user_id=user_id,
            steps=len(plan.steps),
        )

        await emitter.send(
            "plan.created",
            {
                "plan": plan.model_dump(mode="json"),
                "sessionId": plan.session_id,
                "planId": plan.id,
                "userId": user_id,
            },
        )

        return plan

    async def run_plan(
        self,
        *,
        plan_id: str,
        session_id: str,
        user_id: str,
        emitter: ActivityEmitter,
    ) -> PlanWithSteps:
        """Execute the supplied plan sequentially and emit progress activities."""
        await self.initialize()

        plan = await self.orchestrator.get_plan_with_steps(plan_id, session_id)
        if plan is None:
            raise ValueError(f"Plan {plan_id} not found in session {session_id}")

        steps = self._order_steps(plan.steps)
        if not steps:
            logger.warning("Plan contains no executable steps", plan_id=plan_id)
            await emitter.send(
                "exec.completed",
                {
                    "planId": plan_id,
                    "sessionId": session_id,
                    "status": "empty",
                },
            )
            return plan

        for step in steps:
            if step.status in {StepStatus.COMPLETED, StepStatus.FAILED, StepStatus.REJECTED}:
                continue

            await self._emit_step_started(step=step, emitter=emitter)

            result = await self._execute_step(
                plan_id=plan_id,
                session_id=session_id,
                step=step,
                user_id=user_id,
                emitter=emitter,
            )

            plan = await self.orchestrator.get_plan_with_steps(plan_id, session_id) or plan
            step = self._find_step(plan.steps, step.id) or step

            await emitter.send(
                "exec.step.completed",
                {
                    "planId": plan_id,
                    "sessionId": session_id,
                    "step": step.model_dump(mode="json"),
                    "success": result.success,
                },
            )

        updated_plan = await self.orchestrator.get_plan_with_steps(plan_id, session_id) or plan
        await emitter.send(
            "exec.completed",
            {
                "planId": plan_id,
                "sessionId": session_id,
                "plan": updated_plan.model_dump(mode="json"),
            },
        )
        return updated_plan

    async def _emit_step_started(self, *, step: Step, emitter: ActivityEmitter) -> None:
        await emitter.send(
            "exec.step.started",
            {
                "planId": step.plan_id,
                "sessionId": step.session_id,
                "step": step.model_dump(mode="json"),
            },
        )

    async def _execute_step(
        self,
        *,
        plan_id: str,
        session_id: str,
        step: Step,
        user_id: str,
        emitter: ActivityEmitter,
    ) -> ActionResponse:
        feedback = HumanFeedback(
            step_id=step.id,
            plan_id=plan_id,
            session_id=session_id,
            approved=True,
        )

        logger.info(
            "Executing plan step for Microsoft 365 host",
            step_id=step.id,
            plan_id=plan_id,
            session_id=session_id,
            agent=step.agent.value,
        )

        result = await self.orchestrator.handle_step_approval(feedback)

        await emitter.send(
            "exec.step.output",
            {
                "planId": plan_id,
                "sessionId": session_id,
                "stepId": step.id,
                "success": result.success,
                "result": result.result,
                "metadata": result.metadata or {},
            },
        )

        return result

    @staticmethod
    def _order_steps(steps: Iterable[Step]) -> List[Step]:
        return sorted(steps, key=lambda step: ((step.order or 0), step.timestamp))

    @staticmethod
    def _find_step(steps: Iterable[Step], step_id: str) -> Optional[Step]:
        for step in steps:
            if step.id == step_id:
                return step
        return None

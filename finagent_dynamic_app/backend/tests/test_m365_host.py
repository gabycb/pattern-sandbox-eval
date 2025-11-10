import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pytest

from app.infra.settings import Settings
from app.models.task_models import (
    ActionResponse,
    AgentType,
    PlanStatus,
    PlanWithSteps,
    Step,
    StepStatus,
)
from m365.host.adapters import ActivityEmitter, PlannerRunnerAdapter


class _RecorderEmitter(ActivityEmitter):
    def __init__(self) -> None:
        self.events: List[tuple[str, Dict[str, Any]]] = []

    async def send(self, name: str, payload: Dict[str, Any]) -> None:
        self.events.append((name, payload))


@dataclass
class _FakeCosmosStore:
    def __init__(self) -> None:
        self.updated_steps: List[str] = []

    async def initialize(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def add_plan(self, plan) -> None:  # pragma: no cover - unused in test
        return None

    async def add_step(self, step) -> None:  # pragma: no cover - unused in test
        return None

    async def update_step(self, step: Step) -> None:
        self.updated_steps.append(step.id)


class _FakeOrchestrator:
    def __init__(self) -> None:
        self.cosmos = _FakeCosmosStore()
        self._plan: Optional[PlanWithSteps] = None
        self._initialized = False

    async def initialize(self) -> None:
        self._initialized = True

    async def shutdown(self) -> None:  # pragma: no cover - not exercised in test
        return None

    async def create_plan_from_objective(self, task) -> Any:
        plan_id = "plan-test"
        session_id = "session-test"
        user_id = task.user_id or "user-test"
        steps = [
            Step(
                id="step-1",
                plan_id=plan_id,
                session_id=session_id,
                user_id=user_id,
                action="Collect company fundamentals",
                agent=AgentType.COMPANY,
                status=StepStatus.PLANNED,
                order=1,
            ),
            Step(
                id="step-2",
                plan_id=plan_id,
                session_id=session_id,
                user_id=user_id,
                action="Summarize findings",
                agent=AgentType.SUMMARIZER,
                status=StepStatus.PLANNED,
                order=2,
            ),
        ]
        plan = PlanWithSteps(
            id=plan_id,
            session_id=session_id,
            user_id=user_id,
            initial_goal=task.description,
            summary=None,
            overall_status=PlanStatus.IN_PROGRESS,
            human_clarification_request=None,
            human_clarification_response=None,
            total_steps=len(steps),
            completed_steps=0,
            failed_steps=0,
            timestamp=steps[0].timestamp,
            ticker=None,
            scope=None,
            steps=steps,
            steps_requiring_approval=0,
            completed=0,
        )
        self._plan = plan
        return plan

    async def get_plan_with_steps(self, plan_id: str, session_id: str):
        if not self._plan or self._plan.id != plan_id:
            return None

        return PlanWithSteps(
            id=self._plan.id,
            session_id=self._plan.session_id,
            user_id=self._plan.user_id,
            initial_goal=self._plan.initial_goal,
            summary=None,
            overall_status=PlanStatus.IN_PROGRESS,
            human_clarification_request=None,
            human_clarification_response=None,
            total_steps=len(self._plan.steps),
            completed_steps=sum(1 for step in self._plan.steps if step.status == StepStatus.COMPLETED),
            failed_steps=sum(1 for step in self._plan.steps if step.status == StepStatus.FAILED),
            timestamp=self._plan.steps[0].timestamp,
            ticker=None,
            scope=None,
            steps=self._plan.steps,
            steps_requiring_approval=0,
            completed=sum(1 for step in self._plan.steps if step.status == StepStatus.COMPLETED),
        )

    async def handle_step_approval(self, feedback) -> ActionResponse:
        assert self._plan is not None
        step = next(step for step in self._plan.steps if step.id == feedback.step_id)
        step.status = StepStatus.COMPLETED
        await self.cosmos.update_step(step)
        return ActionResponse(
            step_id=step.id,
            plan_id=feedback.plan_id,
            session_id=feedback.session_id,
            success=True,
            result=f"Executed {step.action}",
            metadata={"agent": step.agent.value},
        )


@pytest.mark.asyncio
async def test_planner_runner_adapter_emits_ordered_activities() -> None:
    orchestrator = _FakeOrchestrator()
    adapter = PlannerRunnerAdapter(settings=Settings(), orchestrator=orchestrator)

    emitter = _RecorderEmitter()
    plan = await adapter.create_plan(objective="Research MSFT", user_id="user-123", emitter=emitter)

    assert emitter.events[0][0] == "plan.created"
    assert emitter.events[0][1]["planId"] == plan.id

    emitter.events.clear()

    await adapter.run_plan(
        plan_id=plan.id,
        session_id=plan.session_id,
        user_id="user-123",
        emitter=emitter,
    )

    expected_names = [
        "exec.step.started",
        "exec.step.output",
        "exec.step.completed",
        "exec.step.started",
        "exec.step.output",
        "exec.step.completed",
        "exec.completed",
    ]
    assert [name for name, _ in emitter.events] == expected_names

    assert orchestrator.cosmos.updated_steps == ["step-1", "step-2"]
    assert all(step.status == StepStatus.COMPLETED for step in orchestrator._plan.steps)

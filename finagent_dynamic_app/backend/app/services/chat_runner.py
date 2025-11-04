"""Background sequential execution manager for the chat autorun feature."""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, Iterable, List, Optional, Set

from ..models.chat_models import ChatEventPayload, ChatRunSnapshot
from ..models.task_models import HumanFeedback, PlanStatus, Step, StepStatus
from .chat_pubsub import ChatPubSubPublisher
from .task_orchestrator import TaskOrchestrator

logger = logging.getLogger(__name__)


class ChatRunManager:
    """Coordinates autonomous execution of chat plans."""

    def __init__(self) -> None:
        self._tasks: Dict[str, asyncio.Task] = {}
        self._cancel_signals: Dict[str, asyncio.Event] = {}
        self._task_lock = asyncio.Lock()

    def is_running(self, task_id: str) -> bool:
        """Return True if the task currently has a background worker."""
        task = self._tasks.get(task_id)
        return bool(task) and not task.done()

    async def start_run(
        self,
        *,
        task_id: str,
        session_id: str,
        user_id: str,
        orchestrator: TaskOrchestrator,
        publisher: ChatPubSubPublisher,
    ) -> None:
        """Start sequential execution for the supplied plan if not already running."""
        async with self._task_lock:
            if self.is_running(task_id):
                logger.info("Chat run already active", task_id=task_id)
                return

            cancel_event = asyncio.Event()
            worker = asyncio.create_task(
                self._run_plan(
                    task_id=task_id,
                    session_id=session_id,
                    user_id=user_id,
                    orchestrator=orchestrator,
                    publisher=publisher,
                    cancel_event=cancel_event,
                )
            )
            self._tasks[task_id] = worker
            self._cancel_signals[task_id] = cancel_event
            worker.add_done_callback(lambda _: self._cleanup(task_id))
            logger.info("Chat run started", task_id=task_id)

    async def cancel_run(
        self,
        *,
        task_id: str,
    ) -> bool:
        """Signal cancellation for an in-flight run."""
        cancel_event = self._cancel_signals.get(task_id)
        if cancel_event is None:
            return False

        cancel_event.set()
        logger.info("Cancellation signal raised", task_id=task_id)
        return True

    def _cleanup(self, task_id: str) -> None:
        self._tasks.pop(task_id, None)
        self._cancel_signals.pop(task_id, None)

    async def _run_plan(
        self,
        *,
        task_id: str,
        session_id: str,
        user_id: str,
        orchestrator: TaskOrchestrator,
        publisher: ChatPubSubPublisher,
        cancel_event: asyncio.Event,
    ) -> None:
        """Execute all steps sequentially, publishing updates along the way."""
        logger.info(
            "Autonomous chat execution starting",
            task_id=task_id,
            session_id=session_id,
        )

        processed_messages: Set[str] = set()
        try:
            snapshot = await self._snapshot(orchestrator, task_id, session_id)
            if snapshot is None:
                logger.warning("Plan snapshot unavailable", task_id=task_id)
                return

            await self._publish_plan_state(
                publisher,
                task_id=task_id,
                session_id=session_id,
                event_type="plan_created",
                snapshot=snapshot,
            )
            processed_messages.update(msg.id for msg in snapshot.messages)

            steps = self._order_steps(snapshot.plan.steps)
            for step in steps:
                if cancel_event.is_set():
                    await self._mark_cancelled(orchestrator, publisher, task_id, session_id)
                    return

                # Skip terminal steps (support resumes)
                if step.status in {
                    StepStatus.COMPLETED,
                    StepStatus.FAILED,
                    StepStatus.REJECTED,
                }:
                    continue

                await self._publish_step_event(
                    publisher,
                    task_id=task_id,
                    session_id=session_id,
                    event_type="step_started",
                    step=step,
                )

                feedback = HumanFeedback(
                    step_id=step.id,
                    plan_id=task_id,
                    session_id=session_id,
                    approved=True,
                )

                try:
                    result = await orchestrator.handle_step_approval(feedback)
                    logger.info(
                        "Step executed via autorun",
                        step_id=step.id,
                        task_id=task_id,
                        success=result.success,
                    )
                except Exception as exc:  # pragma: no cover - defensive logging
                    logger.exception("Autonomous step execution failed", step_id=step.id, task_id=task_id)
                    await self._publish_step_event(
                        publisher,
                        task_id=task_id,
                        session_id=session_id,
                        event_type="step_failed",
                        step=step,
                        extra={"error": str(exc)},
                    )
                    await self._mark_failed(orchestrator, publisher, task_id, session_id, error=str(exc))
                    return

                snapshot = await self._snapshot(orchestrator, task_id, session_id)
                if snapshot is None:
                    continue

                await self._publish_plan_state(
                    publisher,
                    task_id=task_id,
                    session_id=session_id,
                    event_type="plan_updated",
                    snapshot=snapshot,
                )

                await self._publish_step_event(
                    publisher,
                    task_id=task_id,
                    session_id=session_id,
                    event_type="step_completed" if result.success else "step_failed",
                    step=self._get_step_by_id(snapshot.plan.steps, step.id) or step,
                    extra={"success": result.success},
                )

                await self._publish_new_messages(
                    orchestrator,
                    publisher,
                    task_id=task_id,
                    session_id=session_id,
                    processed_ids=processed_messages,
                )

            final_snapshot = await self._snapshot(orchestrator, task_id, session_id)
            if final_snapshot:
                await self._publish_plan_state(
                    publisher,
                    task_id=task_id,
                    session_id=session_id,
                    event_type="run_finished",
                    snapshot=final_snapshot,
                )

        finally:
            logger.info("Autonomous chat execution complete", task_id=task_id)

    async def _snapshot(
        self,
        orchestrator: TaskOrchestrator,
        plan_id: str,
        session_id: str,
    ) -> Optional[ChatRunSnapshot]:
        plan = await orchestrator.get_plan_with_steps(plan_id, session_id)
        if not plan:
            return None
        messages = await orchestrator.cosmos.get_messages_by_plan(plan_id)
        return ChatRunSnapshot(plan=plan, messages=messages)

    async def _publish_plan_state(
        self,
        publisher: ChatPubSubPublisher,
        *,
        task_id: str,
        session_id: str,
        event_type: str,
        snapshot: ChatRunSnapshot,
    ) -> None:
        payload = ChatEventPayload(
            type=event_type,  # type: ignore[arg-type]
            task_id=task_id,
            session_id=session_id,
            data={
                "plan": snapshot.plan.model_dump(mode="json"),
            },
        )
        await publisher.send_event(payload)

    async def _publish_step_event(
        self,
        publisher: ChatPubSubPublisher,
        *,
        task_id: str,
        session_id: str,
        event_type: str,
        step: Step,
        extra: Optional[Dict[str, object]] = None,
    ) -> None:
        data = {"step": step.model_dump(mode="json")}
        if extra:
            data.update(extra)
        payload = ChatEventPayload(
            type=event_type,  # type: ignore[arg-type]
            task_id=task_id,
            session_id=session_id,
            data=data,
        )
        await publisher.send_event(payload)

    async def _publish_new_messages(
        self,
        orchestrator: TaskOrchestrator,
        publisher: ChatPubSubPublisher,
        *,
        task_id: str,
        session_id: str,
        processed_ids: Set[str],
    ) -> None:
        messages = await orchestrator.cosmos.get_messages_by_plan(task_id)
        for message in messages:
            if message.id in processed_ids:
                continue
            processed_ids.add(message.id)
            payload = ChatEventPayload(
                type="message",
                task_id=task_id,
                session_id=session_id,
                data={"message": message.model_dump(mode="json")},
            )
            await publisher.send_event(payload)

    async def _mark_cancelled(
        self,
        orchestrator: TaskOrchestrator,
        publisher: ChatPubSubPublisher,
        task_id: str,
        session_id: str,
    ) -> None:
        plan = await orchestrator.cosmos.get_plan(task_id, session_id)
        if plan:
            plan.overall_status = PlanStatus.CANCELLED
            await orchestrator.cosmos.update_plan(plan)
        payload = ChatEventPayload(
            type="run_cancelled",
            task_id=task_id,
            session_id=session_id,
            data={},
        )
        await publisher.send_event(payload)

    async def _mark_failed(
        self,
        orchestrator: TaskOrchestrator,
        publisher: ChatPubSubPublisher,
        task_id: str,
        session_id: str,
        *,
        error: str,
    ) -> None:
        plan = await orchestrator.cosmos.get_plan(task_id, session_id)
        if plan:
            plan.overall_status = PlanStatus.FAILED
            await orchestrator.cosmos.update_plan(plan)
        payload = ChatEventPayload(
            type="run_failed",
            task_id=task_id,
            session_id=session_id,
            data={"error": error},
        )
        await publisher.send_event(payload)

    def _order_steps(self, steps: Iterable[Step]) -> List[Step]:
        return sorted(steps, key=lambda step: (step.order or 0, step.timestamp))

    def _get_step_by_id(self, steps: Iterable[Step], step_id: str) -> Optional[Step]:
        for step in steps:
            if step.id == step_id:
                return step
        return None

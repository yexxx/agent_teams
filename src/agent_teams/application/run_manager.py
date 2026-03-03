from __future__ import annotations

import asyncio
from json import dumps
from typing import Callable, cast

from agent_teams.core.enums import InjectionSource, RunEventType
from agent_teams.core.ids import new_trace_id
from agent_teams.core.models import InjectionMessage, IntentInput, RunEvent, RunResult
from agent_teams.runtime.gate_manager import GateManager
from agent_teams.runtime.injection_manager import RunInjectionManager
from agent_teams.runtime.run_event_hub import RunEventHub
from agent_teams.runtime.tool_approval_manager import ToolApprovalAction, ToolApprovalManager
from agent_teams.state.agent_repo import AgentInstanceRepository


class RunManager:
    def __init__(
        self,
        *,
        meta_agent,
        injection_manager: RunInjectionManager,
        run_event_hub: RunEventHub,
        agent_repo: AgentInstanceRepository,
        gate_manager: GateManager,
        tool_approval_manager: ToolApprovalManager,
    ) -> None:
        self._meta_agent = meta_agent
        self._injection_manager = injection_manager
        self._run_event_hub = run_event_hub
        self._agent_repo = agent_repo
        self._gate_manager = gate_manager
        self._tool_approval_manager = tool_approval_manager
        self._pending_runs: dict[str, IntentInput] = {}
        self._running_run_ids: set[str] = set()

    async def run_intent(
        self,
        intent: IntentInput,
        *,
        ensure_session: Callable[[str | None], str],
    ) -> RunResult:
        intent.session_id = ensure_session(intent.session_id)
        run_id = new_trace_id().value
        self._injection_manager.activate(run_id)
        try:
            return await self._meta_agent.handle_intent(intent, trace_id=run_id)
        finally:
            self._injection_manager.deactivate(run_id)

    def create_run(
        self,
        intent: IntentInput,
        *,
        ensure_session: Callable[[str | None], str],
    ) -> tuple[str, str]:
        intent.session_id = ensure_session(intent.session_id)
        run_id = new_trace_id().value
        self._pending_runs[run_id] = intent
        return run_id, intent.session_id

    def ensure_run_started(self, run_id: str) -> None:
        if run_id in self._running_run_ids:
            return
        intent = self._pending_runs.get(run_id)
        if intent is None:
            raise KeyError(f"Run {run_id} not found")

        self._running_run_ids.add(run_id)
        self._injection_manager.activate(run_id)
        self._run_event_hub.publish(
            RunEvent(
                session_id=intent.session_id,
                run_id=run_id,
                trace_id=run_id,
                task_id=None,
                event_type=RunEventType.RUN_STARTED,
                payload_json=dumps({"session_id": intent.session_id}),
            )
        )

        async def _worker() -> None:
            try:
                result = await self._meta_agent.handle_intent(intent, trace_id=run_id)
                self._run_event_hub.publish(
                    RunEvent(
                        session_id=intent.session_id,
                        run_id=run_id,
                        trace_id=result.trace_id,
                        task_id=result.root_task_id,
                        event_type=RunEventType.RUN_COMPLETED,
                        payload_json=dumps(result.model_dump()),
                    )
                )
            except Exception as exc:
                self._run_event_hub.publish(
                    RunEvent(
                        session_id=intent.session_id,
                        run_id=run_id,
                        trace_id=run_id,
                        task_id=None,
                        event_type=RunEventType.RUN_FAILED,
                        payload_json=dumps({"error": str(exc)}),
                    )
                )
            finally:
                self._injection_manager.deactivate(run_id)
                self._running_run_ids.discard(run_id)
                self._pending_runs.pop(run_id, None)

        asyncio.create_task(_worker())

    async def stream_run_events(self, run_id: str):
        queue = self._run_event_hub.subscribe(run_id)
        self.ensure_run_started(run_id)

        while True:
            event = await queue.get()
            yield event
            if event.event_type in (RunEventType.RUN_COMPLETED, RunEventType.RUN_FAILED):
                self._run_event_hub.unsubscribe_all(run_id)
                break

    async def run_intent_stream(
        self,
        intent: IntentInput,
        *,
        ensure_session: Callable[[str | None], str],
    ):
        run_id, _ = self.create_run(intent, ensure_session=ensure_session)
        async for event in self.stream_run_events(run_id):
            yield event

    def inject_message(
        self,
        run_id: str,
        source: InjectionSource,
        content: str,
    ) -> InjectionMessage:
        running = self._agent_repo.list_running(run_id)
        if not running:
            raise KeyError(f"No RUNNING agent for run_id={run_id}")

        created: InjectionMessage | None = None
        for record in running:
            created = self._injection_manager.enqueue(
                run_id=run_id,
                recipient_instance_id=record.instance_id,
                source=source,
                content=content,
            )
            self._run_event_hub.publish(
                RunEvent(
                    session_id=record.session_id,
                    run_id=run_id,
                    trace_id=run_id,
                    task_id=None,
                    instance_id=record.instance_id,
                    role_id=record.role_id,
                    event_type=RunEventType.INJECTION_ENQUEUED,
                    payload_json=created.model_dump_json(),
                )
            )

        if created is None:
            raise KeyError(f"No RUNNING agent for run_id={run_id}")
        return created

    def resolve_gate(
        self,
        run_id: str,
        task_id: str,
        action: str,
        feedback: str = "",
    ) -> None:
        self._gate_manager.resolve_gate(
            run_id, task_id, action=action, feedback=feedback
        )  # type: ignore[arg-type]

    def list_open_gates(self, run_id: str) -> list[dict]:
        return self._gate_manager.list_open_gates(run_id)

    def resolve_tool_approval(
        self,
        run_id: str,
        tool_call_id: str,
        action: str,
        feedback: str = "",
    ) -> None:
        if action not in {"approve", "deny"}:
            raise ValueError(f"Unsupported action: {action}")
        self._tool_approval_manager.resolve_approval(
            run_id=run_id,
            tool_call_id=tool_call_id,
            action=cast(ToolApprovalAction, action),
            feedback=feedback,
        )

    def list_open_tool_approvals(self, run_id: str) -> list[dict[str, str]]:
        return self._tool_approval_manager.list_open_approvals(run_id=run_id)

    def dispatch_task_human(
        self,
        run_id: str,
        task_id: str,
        coordinator_instance_id: str,
    ) -> None:
        import json

        self._injection_manager.enqueue(
            run_id=run_id,
            recipient_instance_id=coordinator_instance_id,
            source=InjectionSource.USER,
            content=json.dumps({"__human_dispatch__": task_id}),
        )

    def get_coordinator_instance_id(self, session_id: str) -> str | None:
        return self._agent_repo.get_coordinator_instance_id(session_id)

    def dispatch_task_human_for_session(
        self,
        session_id: str,
        run_id: str,
        task_id: str,
    ) -> None:
        coordinator_instance_id = self.get_coordinator_instance_id(session_id)
        if coordinator_instance_id is None:
            raise KeyError(f"No coordinator instance found for session={session_id}")
        self.dispatch_task_human(
            run_id=run_id,
            task_id=task_id,
            coordinator_instance_id=coordinator_instance_id,
        )

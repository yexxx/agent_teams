from __future__ import annotations

import asyncio
from json import dumps
from typing import Callable, cast

from pydantic_ai.messages import ModelRequest, UserPromptPart

from agent_teams.core.enums import InjectionSource, InstanceStatus, RunEventType, TaskStatus
from agent_teams.core.ids import new_trace_id
from agent_teams.core.models import InjectionMessage, IntentInput, RunEvent, RunResult
from agent_teams.runtime.gate_manager import GateManager
from agent_teams.runtime.injection_manager import RunInjectionManager
from agent_teams.runtime.run_control_manager import RunControlManager
from agent_teams.runtime.run_event_hub import RunEventHub
from agent_teams.runtime.tool_approval_manager import ToolApprovalAction, ToolApprovalManager
from agent_teams.state.agent_repo import AgentInstanceRepository
from agent_teams.state.message_repo import MessageRepository
from agent_teams.state.task_repo import TaskRepository


class RunManager:
    def __init__(
        self,
        *,
        meta_agent,
        injection_manager: RunInjectionManager,
        run_event_hub: RunEventHub,
        agent_repo: AgentInstanceRepository,
        task_repo: TaskRepository,
        message_repo: MessageRepository,
        gate_manager: GateManager,
        run_control_manager: RunControlManager,
        tool_approval_manager: ToolApprovalManager,
    ) -> None:
        self._meta_agent = meta_agent
        self._injection_manager = injection_manager
        self._run_event_hub = run_event_hub
        self._agent_repo = agent_repo
        self._task_repo = task_repo
        self._message_repo = message_repo
        self._gate_manager = gate_manager
        self._run_control_manager = run_control_manager
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
        self._ensure_no_paused_subagent(intent.session_id)
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
        self._ensure_no_paused_subagent(intent.session_id)
        run_id = new_trace_id().value
        self._pending_runs[run_id] = intent
        return run_id, intent.session_id

    def _ensure_no_paused_subagent(self, session_id: str) -> None:
        paused = self._run_control_manager.get_paused_subagent(session_id)
        if paused is None:
            return
        raise RuntimeError(
            f'Subagent {paused.role_id} ({paused.instance_id}) is paused in run {paused.run_id}. '
            'Please send a follow-up message to that subagent before messaging the main agent.'
        )

    def ensure_run_started(self, run_id: str) -> None:
        if run_id in self._running_run_ids:
            return
        intent = self._pending_runs.get(run_id)
        if intent is None:
            raise KeyError(f'Run {run_id} not found')

        self._running_run_ids.add(run_id)
        self._injection_manager.activate(run_id)
        self._run_event_hub.publish(
            RunEvent(
                session_id=intent.session_id,
                run_id=run_id,
                trace_id=run_id,
                task_id=None,
                event_type=RunEventType.RUN_STARTED,
                payload_json=dumps({'session_id': intent.session_id}),
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
            except asyncio.CancelledError:
                self._run_event_hub.publish(
                    RunEvent(
                        session_id=intent.session_id,
                        run_id=run_id,
                        trace_id=run_id,
                        task_id=None,
                        event_type=RunEventType.RUN_STOPPED,
                        payload_json=dumps({'reason': 'stopped_by_user'}),
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
                        payload_json=dumps({'error': str(exc)}),
                    )
                )
            finally:
                self._injection_manager.deactivate(run_id)
                self._run_control_manager.unregister_run_task(run_id)
                self._running_run_ids.discard(run_id)
                self._pending_runs.pop(run_id, None)

        task = asyncio.create_task(_worker())
        self._run_control_manager.register_run_task(
            run_id=run_id,
            session_id=intent.session_id,
            task=task,
        )

    async def stream_run_events(self, run_id: str):
        queue = self._run_event_hub.subscribe(run_id)
        self.ensure_run_started(run_id)

        while True:
            event = await queue.get()
            yield event
            if event.event_type in (
                RunEventType.RUN_COMPLETED,
                RunEventType.RUN_FAILED,
                RunEventType.RUN_STOPPED,
            ):
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

    def _publish_injection_event(self, *, run_id: str, record, created: InjectionMessage) -> None:
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

    def inject_message(
        self,
        run_id: str,
        source: InjectionSource,
        content: str,
    ) -> InjectionMessage:
        running = self._agent_repo.list_running(run_id)
        if not running:
            raise KeyError(f'No RUNNING agent for run_id={run_id}')

        created: InjectionMessage | None = None
        for record in running:
            created = self._injection_manager.enqueue(
                run_id=run_id,
                recipient_instance_id=record.instance_id,
                source=source,
                content=content,
            )
            self._publish_injection_event(run_id=run_id, record=record, created=created)

        if created is None:
            raise KeyError(f'No RUNNING agent for run_id={run_id}')
        return created

    def stop_run(self, run_id: str) -> None:
        self._run_control_manager.clear_paused_subagent_for_run(run_id)
        if run_id in self._pending_runs and run_id not in self._running_run_ids:
            intent = self._pending_runs.pop(run_id)
            self._run_event_hub.publish(
                RunEvent(
                    session_id=intent.session_id,
                    run_id=run_id,
                    trace_id=run_id,
                    task_id=None,
                    event_type=RunEventType.RUN_STOPPED,
                    payload_json=dumps({'reason': 'stopped_before_start'}),
                )
            )
            return
        requested = self._run_control_manager.request_run_stop(run_id)
        if not requested and run_id not in self._running_run_ids:
            raise KeyError(f'Run {run_id} not found')

    def _find_task_for_instance(self, *, run_id: str, instance_id: str) -> str | None:
        for record in self._task_repo.list_by_trace(run_id):
            if record.assigned_instance_id != instance_id:
                continue
            if record.status in (
                TaskStatus.RUNNING,
                TaskStatus.ASSIGNED,
                TaskStatus.CREATED,
                TaskStatus.STOPPED,
            ):
                return record.envelope.task_id
        return None

    def stop_subagent(self, run_id: str, instance_id: str) -> dict[str, str]:
        record = self._agent_repo.get_instance(instance_id)
        if record.run_id != run_id:
            raise KeyError(
                f'Instance {instance_id} does not belong to run {run_id}'
            )
        if record.role_id == 'coordinator_agent':
            raise ValueError('Stopping coordinator via subagent API is not allowed')

        paused = self._run_control_manager.request_subagent_stop(
            run_id=run_id,
            instance_id=instance_id,
        )
        if paused is None:
            paused = self._run_control_manager.pause_subagent(
                session_id=record.session_id,
                run_id=run_id,
                instance_id=instance_id,
                role_id=record.role_id,
                task_id=self._find_task_for_instance(run_id=run_id, instance_id=instance_id),
            )
        if paused.task_id:
            self._task_repo.update_status(
                task_id=paused.task_id,
                status=TaskStatus.STOPPED,
                assigned_instance_id=instance_id,
                error_message='Task stopped by user',
            )
        self._agent_repo.mark_status(instance_id, InstanceStatus.STOPPED)

        self._run_event_hub.publish(
            RunEvent(
                session_id=record.session_id,
                run_id=run_id,
                trace_id=run_id,
                task_id=paused.task_id,
                instance_id=instance_id,
                role_id=record.role_id,
                event_type=RunEventType.SUBAGENT_STOPPED,
                payload_json=dumps(
                    {
                        'instance_id': instance_id,
                        'role_id': record.role_id,
                        'task_id': paused.task_id,
                        'reason': paused.reason,
                    }
                ),
            )
        )
        return {
            'status': 'paused',
            'instance_id': instance_id,
            'role_id': record.role_id,
            'task_id': paused.task_id or '',
            'run_id': run_id,
        }

    def inject_subagent_message(
        self,
        *,
        run_id: str,
        instance_id: str,
        content: str,
    ) -> None:
        record = self._agent_repo.get_instance(instance_id)
        if record.run_id != run_id:
            raise KeyError(
                f'Instance {instance_id} does not belong to run {run_id}'
            )

        paused = self._run_control_manager.get_paused_subagent(record.session_id)
        if paused is not None and paused.instance_id != instance_id:
            raise RuntimeError(
                f'Subagent {paused.role_id} ({paused.instance_id}) is paused. '
                'Please continue that paused subagent first.'
            )

        task_id = self._find_task_for_instance(run_id=run_id, instance_id=instance_id)
        if task_id:
            self._task_repo.update_status(
                task_id=task_id,
                status=TaskStatus.ASSIGNED,
                assigned_instance_id=instance_id,
            )
        self._message_repo.append(
            session_id=record.session_id,
            instance_id=instance_id,
            task_id=task_id or 'subagent-followup',
            trace_id=run_id,
            messages=[ModelRequest(parts=[UserPromptPart(content=content)])],
        )

        if self._injection_manager.is_active(run_id) and record.status == InstanceStatus.RUNNING:
            created = self._injection_manager.enqueue(
                run_id=run_id,
                recipient_instance_id=instance_id,
                source=InjectionSource.USER,
                content=content,
            )
            self._publish_injection_event(run_id=run_id, record=record, created=created)

        self._run_control_manager.release_paused_subagent(
            session_id=record.session_id,
            instance_id=instance_id,
        )
        self._agent_repo.mark_status(instance_id, InstanceStatus.IDLE)
        self._run_event_hub.publish(
            RunEvent(
                session_id=record.session_id,
                run_id=run_id,
                trace_id=run_id,
                task_id=task_id,
                instance_id=instance_id,
                role_id=record.role_id,
                event_type=RunEventType.SUBAGENT_RESUMED,
                payload_json=dumps(
                    {
                        'instance_id': instance_id,
                        'role_id': record.role_id,
                        'task_id': task_id,
                    }
                ),
            )
        )

    def resolve_gate(
        self,
        run_id: str,
        task_id: str,
        action: str,
        feedback: str = '',
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
        feedback: str = '',
    ) -> None:
        if action not in {'approve', 'deny'}:
            raise ValueError(f'Unsupported action: {action}')
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
            content=json.dumps({'__human_dispatch__': task_id}),
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
            raise KeyError(f'No coordinator instance found for session={session_id}')
        self.dispatch_task_human(
            run_id=run_id,
            task_id=task_id,
            coordinator_instance_id=coordinator_instance_id,
        )

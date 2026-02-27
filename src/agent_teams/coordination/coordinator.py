from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from agent_teams.agents.instance_pool import InstancePool
from agent_teams.agents.subagent import SubAgentRunner
from agent_teams.core.enums import EventType, InstanceStatus, ScopeType, TaskStatus
from agent_teams.core.ids import new_task_id, new_trace_id
from agent_teams.core.models import EventEnvelope, IntentInput, RoleDefinition, ScopeRef, TaskEnvelope, VerificationPlan
from agent_teams.events.event_bus import EventBus
from agent_teams.prompting.runtime_prompt_builder import RuntimePromptBuilder
from agent_teams.providers.llm import LLMProvider
from agent_teams.roles.registry import RoleRegistry
from agent_teams.state.agent_repo import AgentInstanceRepository
from agent_teams.state.shared_store import SharedStore
from agent_teams.state.task_repo import TaskRepository
from agent_teams.tools.verify_task.impl import verify_task

ROLE_COORDINATOR = 'coordinator_agent'
MAX_ORCHESTRATION_CYCLES = 8


@dataclass
class CoordinatorGraph:
    role_registry: RoleRegistry
    instance_pool: InstancePool
    task_repo: TaskRepository
    shared_store: SharedStore
    event_bus: EventBus
    agent_repo: AgentInstanceRepository
    prompt_builder: RuntimePromptBuilder
    provider_factory: Callable[[RoleDefinition], LLMProvider]

    def run(self, intent: IntentInput, trace_id: str | None = None) -> tuple[str, str, str, str]:
        trace_id = trace_id or new_trace_id().value
        self.role_registry.get(ROLE_COORDINATOR)

        root_task = TaskEnvelope(
            task_id=new_task_id().value,
            session_id=intent.session_id,
            parent_task_id=None,
            trace_id=trace_id,
            objective=intent.intent,
            parent_instruction=(
                'You are the workflow coordinator. For complex requests, orchestrate subagents by creating and assigning '
                'tasks (typically spec_builder -> design_builder -> coder -> verify). For simple requests like greetings, '
                'respond directly without heavy orchestration.'
            ),
            scope=('end_to_end_delivery',),
            dod=('response produced',),
            verification=VerificationPlan(checklist=('non_empty_response',)),
        )
        self.task_repo.create(root_task)
        self.event_bus.emit(
            EventEnvelope(
                event_type=EventType.TASK_CREATED,
                trace_id=trace_id,
                session_id=intent.session_id,
                task_id=root_task.task_id,
                payload_json='{}',
            )
        )

        coordinator_instance_id = self._create_instance(
            role_id=ROLE_COORDINATOR,
            task=root_task,
            session_id=intent.session_id,
            trace_id=trace_id,
        )

        coordinator_result = self._task_executor(
            instance_id=coordinator_instance_id,
            role_id=ROLE_COORDINATOR,
            task=root_task,
        )

        cycle = 0
        while cycle < MAX_ORCHESTRATION_CYCLES:
            cycle += 1
            ran_any = self._run_pending_delegated_tasks(trace_id=trace_id, root_task_id=root_task.task_id)
            if not ran_any:
                break
            coordinator_result = self._task_executor(
                instance_id=coordinator_instance_id,
                role_id=ROLE_COORDINATOR,
                task=root_task,
            )

        verification = verify_task(self.task_repo, self.event_bus, root_task.task_id)
        status = 'completed' if verification.passed else 'failed'
        return trace_id, root_task.task_id, status, coordinator_result

    def _run_pending_delegated_tasks(self, trace_id: str, root_task_id: str) -> bool:
        records = self.task_repo.list_by_trace(trace_id)
        ran_any = False
        for record in records:
            task = record.envelope
            if task.task_id == root_task_id:
                continue
            if record.status not in (TaskStatus.ASSIGNED, TaskStatus.CREATED):
                continue
            if record.assigned_instance_id is None:
                continue
            instance = self.instance_pool.get(record.assigned_instance_id)
            self._task_executor(
                instance_id=instance.instance_id,
                role_id=instance.role_id,
                task=task,
            )
            ran_any = True
        return ran_any

    def _create_instance(self, role_id: str, task: TaskEnvelope, session_id: str, trace_id: str) -> str:
        instance = self.instance_pool.create_subagent(role_id)
        self.task_repo.update_status(
            task_id=task.task_id,
            status=TaskStatus.ASSIGNED,
            assigned_instance_id=instance.instance_id,
        )
        self.agent_repo.upsert_instance(
            run_id=trace_id,
            trace_id=trace_id,
            session_id=session_id,
            instance_id=instance.instance_id,
            role_id=role_id,
            status=InstanceStatus.IDLE,
        )
        self.event_bus.emit(
            EventEnvelope(
                event_type=EventType.INSTANCE_CREATED,
                trace_id=trace_id,
                session_id=session_id,
                task_id=task.task_id,
                instance_id=instance.instance_id,
                payload_json='{}',
            )
        )
        self.event_bus.emit(
            EventEnvelope(
                event_type=EventType.TASK_ASSIGNED,
                trace_id=trace_id,
                session_id=session_id,
                task_id=task.task_id,
                instance_id=instance.instance_id,
                payload_json='{}',
            )
        )
        return instance.instance_id

    def _task_executor(
        self,
        instance_id: str,
        role_id: str,
        task: TaskEnvelope,
    ) -> str:
        self.instance_pool.mark_running(instance_id)
        self.agent_repo.mark_status(instance_id, InstanceStatus.RUNNING)
        self.task_repo.update_status(task.task_id, TaskStatus.RUNNING)
        self.event_bus.emit(
            EventEnvelope(
                event_type=EventType.TASK_STARTED,
                trace_id=task.trace_id,
                session_id=task.session_id,
                task_id=task.task_id,
                instance_id=instance_id,
                payload_json='{}',
            )
        )

        role = self.role_registry.get(role_id)
        runner = SubAgentRunner(role=role, prompt_builder=self.prompt_builder, provider=self.provider_factory(role))
        snapshot = self.shared_store.snapshot(ScopeRef(scope_type=ScopeType.SESSION, scope_id=task.session_id))
        try:
            result = runner.run(
                task=task,
                instance_id=instance_id,
                parent_instruction=task.parent_instruction,
                shared_state_snapshot=snapshot,
            )
            self.task_repo.update_status(task.task_id, TaskStatus.COMPLETED, result=result)
            self.instance_pool.mark_completed(instance_id)
            self.agent_repo.mark_status(instance_id, InstanceStatus.COMPLETED)
            self.event_bus.emit(
                EventEnvelope(
                    event_type=EventType.TASK_COMPLETED,
                    trace_id=task.trace_id,
                    session_id=task.session_id,
                    task_id=task.task_id,
                    instance_id=instance_id,
                    payload_json='{}',
                )
            )
            return result
        except TimeoutError:
            self.task_repo.update_status(task.task_id, TaskStatus.TIMEOUT, error_message='Task timeout')
            self.instance_pool.mark_timeout(instance_id)
            self.agent_repo.mark_status(instance_id, InstanceStatus.TIMEOUT)
            self.event_bus.emit(
                EventEnvelope(
                    event_type=EventType.TASK_TIMEOUT,
                    trace_id=task.trace_id,
                    session_id=task.session_id,
                    task_id=task.task_id,
                    instance_id=instance_id,
                    payload_json='{}',
                )
            )
            raise
        except Exception as exc:
            self.task_repo.update_status(task.task_id, TaskStatus.FAILED, error_message=str(exc))
            self.instance_pool.mark_failed(instance_id)
            self.agent_repo.mark_status(instance_id, InstanceStatus.FAILED)
            self.event_bus.emit(
                EventEnvelope(
                    event_type=EventType.TASK_FAILED,
                    trace_id=task.trace_id,
                    session_id=task.session_id,
                    task_id=task.task_id,
                    instance_id=instance_id,
                    payload_json='{}',
                )
            )
            raise

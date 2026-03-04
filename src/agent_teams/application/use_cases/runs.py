from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import AsyncGenerator

from agent_teams.application.run_manager import RunManager
from agent_teams.core.enums import InjectionSource
from agent_teams.core.models import InjectionMessage, IntentInput, RunEvent, RunResult
from agent_teams.state.session_repo import SessionRepository


@dataclass(slots=True)
class RunUseCases:
    run_manager: RunManager
    session_repo: SessionRepository

    def ensure_session(self, session_id: str | None) -> str:
        if not session_id:
            new_id = f"session-{uuid.uuid4().hex[:8]}"
            self.session_repo.create(session_id=new_id)
            return new_id
        try:
            self.session_repo.get(session_id)
            return session_id
        except KeyError:
            self.session_repo.create(session_id=session_id)
            return session_id

    async def run_intent(self, intent: IntentInput) -> RunResult:
        return await self.run_manager.run_intent(intent, ensure_session=self.ensure_session)

    def create_run(self, intent: IntentInput) -> tuple[str, str]:
        return self.run_manager.create_run(intent, ensure_session=self.ensure_session)

    def ensure_run_started(self, run_id: str) -> None:
        self.run_manager.ensure_run_started(run_id)

    async def stream_run_events(self, run_id: str) -> AsyncGenerator[RunEvent, None]:
        async for event in self.run_manager.stream_run_events(run_id):
            yield event

    async def run_intent_stream(self, intent: IntentInput) -> AsyncGenerator[RunEvent, None]:
        async for event in self.run_manager.run_intent_stream(
            intent,
            ensure_session=self.ensure_session,
        ):
            yield event

    def inject_message(
        self,
        run_id: str,
        source: InjectionSource,
        content: str,
    ) -> InjectionMessage:
        return self.run_manager.inject_message(run_id, source, content)

    def resolve_gate(self, run_id: str, task_id: str, action: str, feedback: str = "") -> None:
        self.run_manager.resolve_gate(run_id, task_id, action, feedback)

    def list_open_gates(self, run_id: str) -> list[dict]:
        return self.run_manager.list_open_gates(run_id)

    def resolve_tool_approval(
        self,
        run_id: str,
        tool_call_id: str,
        action: str,
        feedback: str = "",
    ) -> None:
        self.run_manager.resolve_tool_approval(run_id, tool_call_id, action, feedback)

    def list_open_tool_approvals(self, run_id: str) -> list[dict[str, str]]:
        return self.run_manager.list_open_tool_approvals(run_id)

    def dispatch_task_human(self, run_id: str, task_id: str, coordinator_instance_id: str) -> None:
        self.run_manager.dispatch_task_human(run_id, task_id, coordinator_instance_id)

    def get_coordinator_instance_id(self, session_id: str) -> str | None:
        return self.run_manager.get_coordinator_instance_id(session_id)

    def dispatch_task_human_for_session(self, session_id: str, run_id: str, task_id: str) -> None:
        self.run_manager.dispatch_task_human_for_session(session_id, run_id, task_id)

    def stop_run(self, run_id: str) -> None:
        self.run_manager.stop_run(run_id)

    def stop_subagent(self, run_id: str, instance_id: str) -> dict[str, str]:
        return self.run_manager.stop_subagent(run_id, instance_id)

    def inject_subagent_message(self, run_id: str, instance_id: str, content: str) -> None:
        self.run_manager.inject_subagent_message(
            run_id=run_id,
            instance_id=instance_id,
            content=content,
        )

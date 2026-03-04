from __future__ import annotations

from dataclasses import dataclass

from agent_teams.application.rounds_projection import find_round_by_run_id, paginate_rounds
from agent_teams.application.session_service import SessionService
from agent_teams.core.models import AgentRuntimeRecord, SessionRecord


@dataclass(slots=True)
class SessionUseCases:
    session_service: SessionService

    def create_session(
        self,
        session_id: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> SessionRecord:
        return self.session_service.create_session(session_id=session_id, metadata=metadata)

    def update_session(self, session_id: str, metadata: dict[str, str]) -> None:
        self.session_service.update_session(session_id, metadata)

    def delete_session(self, session_id: str) -> None:
        self.session_service.delete_session(session_id)

    def get_session(self, session_id: str) -> SessionRecord:
        return self.session_service.get_session(session_id)

    def list_sessions(self) -> tuple[SessionRecord, ...]:
        return self.session_service.list_sessions()

    def list_agents_in_session(self, session_id: str) -> tuple[AgentRuntimeRecord, ...]:
        return self.session_service.list_agents_in_session(session_id)

    def get_agent_messages(self, session_id: str, instance_id: str) -> list[dict]:
        return self.session_service.get_agent_messages(session_id, instance_id)

    def get_global_events(self, session_id: str) -> list[dict]:
        return self.session_service.get_global_events(session_id)

    def get_session_messages(self, session_id: str) -> list[dict]:
        return self.session_service.get_session_messages(session_id)

    def get_session_workflows(self, session_id: str) -> list[dict]:
        return self.session_service.get_session_workflows(session_id)

    def build_session_rounds(self, session_id: str) -> list[dict]:
        return self.session_service.build_session_rounds(session_id)

    def get_session_rounds(
        self,
        session_id: str,
        *,
        limit: int = 8,
        cursor_run_id: str | None = None,
    ) -> dict[str, object]:
        rounds = self.build_session_rounds(session_id)
        return paginate_rounds(rounds, limit=limit, cursor_run_id=cursor_run_id)

    def get_round(self, session_id: str, run_id: str) -> dict:
        rounds = self.build_session_rounds(session_id)
        return find_round_by_run_id(rounds, session_id=session_id, run_id=run_id)

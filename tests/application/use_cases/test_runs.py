from __future__ import annotations

from dataclasses import dataclass

from agent_teams.application.use_cases.runs import RunUseCases


@dataclass
class _FakeSessionRecord:
    session_id: str


class _FakeSessionRepo:
    def __init__(self) -> None:
        self._sessions: set[str] = set()

    def create(self, session_id: str, metadata: dict[str, str] | None = None) -> _FakeSessionRecord:
        self._sessions.add(session_id)
        return _FakeSessionRecord(session_id=session_id)

    def get(self, session_id: str) -> _FakeSessionRecord:
        if session_id not in self._sessions:
            raise KeyError(session_id)
        return _FakeSessionRecord(session_id=session_id)


class _FakeRunManager:
    def __init__(self) -> None:
        self.called_with_session_id: str | None = None

    async def run_intent(self, intent, *, ensure_session):
        self.called_with_session_id = ensure_session(intent.session_id)
        return "ok"


def test_ensure_session_creates_when_missing() -> None:
    use_case = RunUseCases(run_manager=_FakeRunManager(), session_repo=_FakeSessionRepo())

    session_id = use_case.ensure_session(None)

    assert session_id.startswith("session-")


def test_ensure_session_creates_when_unknown() -> None:
    repo = _FakeSessionRepo()
    use_case = RunUseCases(run_manager=_FakeRunManager(), session_repo=repo)

    session_id = use_case.ensure_session("session-abc")

    assert session_id == "session-abc"
    assert repo.get("session-abc").session_id == "session-abc"

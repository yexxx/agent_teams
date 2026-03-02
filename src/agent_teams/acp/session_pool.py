from __future__ import annotations

from dataclasses import dataclass
from threading import Lock

from agent_teams.acp.session_client import SessionHandle


@dataclass(frozen=True)
class SessionBinding:
    client_id: str
    handle: SessionHandle


class AcpSessionPool:
    def __init__(self) -> None:
        self._lock = Lock()
        self._bindings: dict[str, SessionBinding] = {}

    def get(self, instance_id: str) -> SessionBinding | None:
        with self._lock:
            return self._bindings.get(instance_id)

    def set(self, instance_id: str, binding: SessionBinding) -> None:
        with self._lock:
            self._bindings[instance_id] = binding

    def pop(self, instance_id: str) -> SessionBinding | None:
        with self._lock:
            return self._bindings.pop(instance_id, None)

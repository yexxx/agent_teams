from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class SessionInitSpec:
    run_id: str
    trace_id: str
    task_id: str
    session_id: str
    instance_id: str
    role_id: str
    system_prompt: str
    tools: tuple[dict[str, object], ...] = ()
    skills: tuple[dict[str, object], ...] = ()
    mcp_servers: tuple[dict[str, object], ...] = ()


@dataclass(frozen=True)
class TurnInput:
    user_prompt: str


@dataclass(frozen=True)
class TurnOutput:
    text: str
    tool_calls: tuple[dict[str, object], ...] = ()
    tool_results: tuple[dict[str, object], ...] = ()


@dataclass(frozen=True)
class SessionHandle:
    session_id: str
    instance_id: str
    metadata: dict[str, object] = field(default_factory=dict)


class AgentSessionClient(Protocol):
    async def open(self, spec: SessionInitSpec) -> SessionHandle: ...

    async def run_turn(self, handle: SessionHandle, turn: TurnInput) -> TurnOutput: ...

    async def close(self, handle: SessionHandle) -> None: ...

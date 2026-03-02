from __future__ import annotations

from dataclasses import dataclass

from agent_teams.acp.session_client import SessionHandle, SessionInitSpec, TurnInput, TurnOutput
from agent_teams.providers.llm import LLMProvider, LLMRequest


@dataclass
class LocalWrappedSessionClient:
    delegate: LLMProvider

    async def open(self, spec: SessionInitSpec) -> SessionHandle:
        return SessionHandle(
            session_id=f"local:{spec.instance_id}",
            instance_id=spec.instance_id,
            metadata={
                "run_id": spec.run_id,
                "trace_id": spec.trace_id,
                "task_id": spec.task_id,
                "session_id": spec.session_id,
                "role_id": spec.role_id,
                "system_prompt": spec.system_prompt,
            },
        )

    async def run_turn(self, handle: SessionHandle, turn: TurnInput) -> TurnOutput:
        run_id = str(handle.metadata.get("run_id", ""))
        trace_id = str(handle.metadata.get("trace_id", ""))
        task_id = str(handle.metadata.get("task_id", ""))
        session_id = str(handle.metadata.get("session_id", ""))
        role_id = str(handle.metadata.get("role_id", ""))
        system_prompt = str(handle.metadata.get("system_prompt", ""))
        text = await self.delegate.generate(
            LLMRequest(
                run_id=run_id,
                trace_id=trace_id,
                task_id=task_id,
                session_id=session_id,
                instance_id=handle.instance_id,
                role_id=role_id,
                system_prompt=system_prompt,
                user_prompt=turn.user_prompt,
            )
        )
        return TurnOutput(text=text)

    async def close(self, handle: SessionHandle) -> None:
        return None

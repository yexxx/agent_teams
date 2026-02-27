from __future__ import annotations

import uuid

from pydantic_ai import Agent

from agent_teams.core.models import TaskEnvelope, VerificationPlan
from agent_teams.tools.runtime import ToolDeps
from agent_teams.tools.tool_helpers import execute_tool


def mount(agent: Agent[ToolDeps, str]) -> None:
    @agent.tool
    def create_task(
        ctx,
        objective: str,
        scope: list[str],
        dod: list[str],
        verification_checklist: list[str],
        parent_task_id: str | None = None,
        parent_instruction: str | None = None,
    ) -> str:
        def _action() -> str:
            task_id = f"task_{uuid.uuid4().hex[:12]}"
            envelope = TaskEnvelope(
                task_id=task_id,
                session_id=ctx.deps.session_id,
                trace_id=ctx.deps.trace_id,
                parent_task_id=parent_task_id,
                objective=objective,
                parent_instruction=parent_instruction,
                scope=tuple(scope),
                dod=tuple(dod),
                verification=VerificationPlan(checklist=tuple(verification_checklist)),
            )
            ctx.deps.task_repo.create(envelope)
            return envelope.task_id

        return execute_tool(
            ctx,
            tool_name='create_task',
            args_summary={
                'objective_len': len(objective),
                'scope_count': len(scope),
                'dod_count': len(dod),
                'verification_count': len(verification_checklist),
                'parent_task_id': parent_task_id,
                'has_parent_instruction': bool(parent_instruction),
            },
            action=_action,
        )

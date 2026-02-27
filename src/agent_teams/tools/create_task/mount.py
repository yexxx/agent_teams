from __future__ import annotations

import uuid

from pydantic_ai import Agent

from agent_teams.core.models import TaskEnvelope, VerificationPlan
from agent_teams.tools.runtime import ToolDeps
from agent_teams.tools.tool_helpers import emit_tool_call, emit_tool_result, with_injections


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
        emit_tool_call(ctx, 'create_task')
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
        result = with_injections(ctx, envelope.task_id)
        emit_tool_result(ctx, 'create_task')
        return result

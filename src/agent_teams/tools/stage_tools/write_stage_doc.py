# -*- coding: utf-8 -*-
from __future__ import annotations

from pydantic_ai import Agent

from agent_teams.shared_types.json_types import JsonObject
from agent_teams.tools.runtime import ToolContext, ToolDeps, execute_tool


def register(agent: Agent[ToolDeps, str]) -> None:
    @agent.tool
    async def write_stage_doc(ctx: ToolContext, content: str) -> JsonObject:
        def _action() -> str:
            if not content.strip():
                raise ValueError("content must not be empty")
            path = ctx.deps.workspace.artifacts.current_stage_doc_path(
                run_id=ctx.deps.run_id,
                role_id=ctx.deps.role_id,
            )
            ctx.deps.workspace.artifacts.write_stage_doc_once(
                path=path,
                content=content,
            )
            return str(path.relative_to(ctx.deps.workspace.locations.workspace_dir))

        return await execute_tool(
            ctx,
            tool_name="write_stage_doc",
            args_summary={"role_id": ctx.deps.role_id, "content_len": len(content)},
            action=_action,
        )

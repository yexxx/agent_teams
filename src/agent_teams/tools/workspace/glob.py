from __future__ import annotations

from pydantic_ai import Agent

from agent_teams.tools.file_utils import resolve_workspace_path
from agent_teams.tools.runtime import ToolContext, ToolDeps
from agent_teams.tools.tool_helpers import execute_tool


def register(agent: Agent[ToolDeps, str]) -> None:
    @agent.tool
    async def glob(ctx: ToolContext, pattern: str) -> dict[str, object]:
        def _action() -> str:
            root = resolve_workspace_path(ctx.deps.workspace_root, '.')
            matches = [str(path.relative_to(root)) for path in root.rglob(pattern)]
            return '\n'.join(matches[:500])

        return await execute_tool(
            ctx,
            tool_name='glob',
            args_summary={'pattern': pattern},
            action=_action,
        )


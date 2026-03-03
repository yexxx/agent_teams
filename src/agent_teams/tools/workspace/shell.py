from __future__ import annotations

from pydantic_ai import Agent

from agent_teams.tools.runtime import ToolContext, ToolDeps
from agent_teams.tools.tool_helpers import execute_tool
from agent_teams.tools.workspace.shell_executor import run_git_bash
from agent_teams.tools.workspace.shell_policy import normalize_timeout, validate_shell_command

MAX_OUTPUT_CHARS = 64_000


def register(agent: Agent[ToolDeps, str]) -> None:
    @agent.tool
    async def shell(
        ctx: ToolContext, command: str, timeout_seconds: int | None = None
    ) -> dict[str, object]:
        def _action() -> dict[str, object]:
            validate_shell_command(command)
            timeout = normalize_timeout(timeout_seconds)
            code, stdout, stderr, timed_out = run_git_bash(
                command=command,
                workdir=ctx.deps.workspace_root,
                timeout_seconds=timeout,
            )
            return {
                'ok': code == 0,
                'exit_code': code,
                'timed_out': timed_out,
                'stdout': stdout[:MAX_OUTPUT_CHARS],
                'stderr': stderr[:MAX_OUTPUT_CHARS],
            }

        return await execute_tool(
            ctx,
            tool_name='shell',
            args_summary={'command': command[:160], 'timeout_seconds': timeout_seconds},
            action=_action,
        )


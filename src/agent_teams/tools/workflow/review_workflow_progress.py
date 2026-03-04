from __future__ import annotations

from pydantic_ai import Agent

from agent_teams.core.enums import TaskStatus
from agent_teams.core.types import JsonObject
from agent_teams.tools.runtime import ToolContext, ToolDeps
from agent_teams.tools.tool_helpers import execute_tool
from agent_teams.workflow.runtime_graph import decide_review_action, load_graph, normalize_strategy


def register(agent: Agent[ToolDeps, str]) -> None:
    @agent.tool
    async def review_workflow_progress(ctx: ToolContext, workflow_id: str) -> dict[str, object]:
        def _action() -> JsonObject:
            graph = load_graph(ctx.deps.shared_store, task_id=ctx.deps.task_id)
            if graph is None:
                raise KeyError('workflow_graph not found, call create_workflow_graph first')
            if graph.get('workflow_id') != workflow_id:
                raise ValueError(
                    f'workflow_id mismatch: expected {graph.get("workflow_id")}, got {workflow_id}'
                )

            records = {
                record.envelope.task_id: record
                for record in ctx.deps.task_repo.list_by_trace(ctx.deps.trace_id)
            }
            decision = decide_review_action(graph=graph, task_records=records)
            strategy = normalize_strategy(graph)

            total = 0
            completed = 0
            failed = 0
            pending = 0
            for task_info_raw in graph.get('tasks', {}).values() if isinstance(graph.get('tasks', {}), dict) else []:
                if not isinstance(task_info_raw, dict):
                    continue
                task_id_raw = task_info_raw.get('task_id')
                if not isinstance(task_id_raw, str) or not task_id_raw:
                    continue
                total += 1
                record = records.get(task_id_raw)
                if record is None:
                    pending += 1
                    continue
                if record.status == TaskStatus.COMPLETED:
                    completed += 1
                elif record.status in (TaskStatus.FAILED, TaskStatus.TIMEOUT):
                    failed += 1
                elif record.status in (TaskStatus.CREATED, TaskStatus.ASSIGNED, TaskStatus.RUNNING):
                    pending += 1

            return {
                'ok': True,
                'workflow_id': workflow_id,
                'strategy': strategy,
                'review_action': decision,
                'progress': {
                    'total': total,
                    'completed': completed,
                    'failed': failed,
                    'pending': pending,
                },
                'next_action': _next_action(decision),
            }

        return await execute_tool(
            ctx,
            tool_name='review_workflow_progress',
            args_summary={'workflow_id': workflow_id},
            action=_action,
        )


def _next_action(review_action: str) -> str:
    if review_action == 'finish':
        return 'finalize'
    if review_action == 'replan':
        return 'adjust_plan'
    return 'continue_dispatch'

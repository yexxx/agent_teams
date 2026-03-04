from __future__ import annotations

from typing import Literal

from pydantic_ai import Agent

from agent_teams.core.types import JsonObject
from agent_teams.tools.runtime import ToolContext, ToolDeps
from agent_teams.tools.tool_helpers import execute_tool
from agent_teams.workflow.runtime_graph import load_graph, normalize_strategy, save_graph

OrchestratorType = Literal['ai', 'human']
PlanningMode = Literal['sop', 'freeform']
ReviewState = Literal['review', 'replan', 'finish']


def register(agent: Agent[ToolDeps, str]) -> None:
    @agent.tool
    async def set_workflow_strategy(
        ctx: ToolContext,
        workflow_id: str,
        orchestrator: OrchestratorType = 'ai',
        planning_mode: PlanningMode = 'sop',
        review_state: ReviewState = 'review',
        note: str = '',
    ) -> dict[str, object]:
        def _action() -> JsonObject:
            graph = load_graph(ctx.deps.shared_store, task_id=ctx.deps.task_id)
            if graph is None:
                raise KeyError('workflow_graph not found, call create_workflow_graph first')
            if graph.get('workflow_id') != workflow_id:
                raise ValueError(
                    f'workflow_id mismatch: expected {graph.get("workflow_id")}, got {workflow_id}'
                )

            graph['orchestrator'] = orchestrator
            graph['planning_mode'] = planning_mode
            graph['review_state'] = review_state
            graph['strategy_note'] = note.strip()
            save_graph(ctx.deps.shared_store, task_id=ctx.deps.task_id, graph=graph)

            normalized = normalize_strategy(graph)
            response: JsonObject = {
                'ok': True,
                'workflow_id': workflow_id,
                'strategy': normalized,
            }
            if graph['strategy_note']:
                response['strategy_note'] = str(graph['strategy_note'])
            return response

        return await execute_tool(
            ctx,
            tool_name='set_workflow_strategy',
            args_summary={
                'workflow_id': workflow_id,
                'orchestrator': orchestrator,
                'planning_mode': planning_mode,
                'review_state': review_state,
                'note_length': len(note),
            },
            action=_action,
        )

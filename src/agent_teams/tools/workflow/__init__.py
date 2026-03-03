from __future__ import annotations

from agent_teams.tools.workflow.create_workflow_graph import register as register_create_workflow_graph
from agent_teams.tools.workflow.dispatch_ready_tasks import register as register_dispatch_ready_tasks
from agent_teams.tools.workflow.get_workflow_status import register as register_get_workflow_status
from agent_teams.tools.workflow.list_available_roles import register as register_list_available_roles

TOOLS = {
    'list_available_roles': register_list_available_roles,
    'create_workflow_graph': register_create_workflow_graph,
    'dispatch_ready_tasks': register_dispatch_ready_tasks,
    'get_workflow_status': register_get_workflow_status,
}

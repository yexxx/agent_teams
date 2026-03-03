from agent_teams.tools.stage import TOOLS as STAGE_TOOLS
from agent_teams.tools.workflow import TOOLS as WORKFLOW_TOOLS
from agent_teams.tools.workspace import TOOLS as WORKSPACE_TOOLS
from agent_teams.tools.registry import ToolRegistry


def build_default_registry() -> ToolRegistry:
    tools = {
        **WORKFLOW_TOOLS,
        **WORKSPACE_TOOLS,
        **STAGE_TOOLS,
    }
    return ToolRegistry(tools)

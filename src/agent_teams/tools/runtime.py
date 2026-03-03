from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic_ai import RunContext

from agent_teams.agents.management.instance_pool import InstancePool
from agent_teams.state.event_log import EventLog
from agent_teams.runtime.injection_manager import RunInjectionManager
from agent_teams.runtime.run_event_hub import RunEventHub
from agent_teams.state.agent_repo import AgentInstanceRepository
from agent_teams.state.shared_store import SharedStore
from agent_teams.state.task_repo import TaskRepository

if TYPE_CHECKING:
    from agent_teams.coordination.task_execution_service import TaskExecutionService
    from agent_teams.roles.registry import RoleRegistry
    from agent_teams.runtime.run_control_manager import RunControlManager
    from agent_teams.runtime.tool_approval_manager import ToolApprovalManager
    from agent_teams.tools.policy import ToolApprovalPolicy


@dataclass(frozen=True)
class ToolDeps:
    task_repo: TaskRepository
    instance_pool: InstancePool
    shared_store: SharedStore
    event_bus: EventLog
    injection_manager: RunInjectionManager
    run_event_hub: RunEventHub
    agent_repo: AgentInstanceRepository
    workspace_root: Path
    run_id: str
    trace_id: str
    task_id: str
    session_id: str
    instance_id: str
    role_id: str
    role_registry: 'RoleRegistry'
    task_execution_service: 'TaskExecutionService'
    run_control_manager: 'RunControlManager'
    tool_approval_manager: 'ToolApprovalManager'
    tool_approval_policy: 'ToolApprovalPolicy'


ToolContext = RunContext[ToolDeps]

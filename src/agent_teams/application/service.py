from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_teams.core.config import load_runtime_config
from agent_teams.core.enums import InjectionSource
from agent_teams.core.models import (
    InjectionMessage,
    AgentRuntimeRecord,
    IntentInput,
    RoleDefinition,
    RunResult,
    SessionRecord,
    SubAgentInstance,
    TaskEnvelope,
    TaskRecord,
)
from agent_teams.composition.bootstrap import build_service_components
from agent_teams.application.rounds_projection import (
    collect_pending_stream_snapshots,
    collect_pending_tool_approvals,
)
from agent_teams.application.provider_runtime import (
    create_provider_factory,
    create_task_execution_service,
)
from agent_teams.application.run_manager import RunManager
from agent_teams.application.session_service import SessionService
from agent_teams.application.task_service import TaskService
from agent_teams.application.use_cases import RunUseCases, SessionUseCases, TaskUseCases
from agent_teams.runtime.console import set_debug
from agent_teams.workflow.spec import WorkflowSpec


def _get_project_root() -> Path:
    return Path(__file__).parent.parent.parent.parent.parent


class AgentTeamsService:
    def __init__(
        self,
        roles_dir: Path | None = None,
        db_path: Path | None = None,
        config_dir: Path = _get_project_root() / ".agent_teams",
        debug: bool = False,
    ) -> None:
        set_debug(debug)
        components = build_service_components(
            config_dir=config_dir,
            roles_dir=roles_dir,
            db_path=db_path,
        )

        self._meta_agent = components.meta_agent
        self._task_repo = components.task_repo
        self._instance_pool = components.instance_pool
        self._role_registry = components.role_registry
        self._workflows: list[WorkflowSpec] = []
        self._injection_manager = components.injection_manager
        self._run_control_manager = components.run_control_manager
        self._run_event_hub = components.run_event_hub
        self._gate_manager = components.gate_manager
        self._tool_approval_manager = components.tool_approval_manager
        self._tool_approval_policy = components.tool_approval_policy
        self._agent_repo = components.agent_repo
        self._session_repo = components.session_repo
        self._message_repo = components.message_repo
        self._event_log = components.event_log
        self._shared_store = components.shared_store
        self._config_dir = config_dir
        self._config_manager = components.config_manager
        self._roles_dir = components.runtime.paths.roles_dir
        self._db_path = components.runtime.paths.db_path
        self._runtime = components.runtime
        self._mcp_registry = components.mcp_registry
        self._skill_registry = components.skill_registry
        self._tool_registry = components.tool_registry
        self._provider_factory = components.provider_factory
        self._task_execution_service = components.task_execution_service
        self._run_manager = RunManager(
            meta_agent=self._meta_agent,
            injection_manager=self._injection_manager,
            run_event_hub=self._run_event_hub,
            gate_manager=self._gate_manager,
            run_control_manager=self._run_control_manager,
            tool_approval_manager=self._tool_approval_manager,
        )
        self._session_service = SessionService(
            session_repo=self._session_repo,
            task_repo=self._task_repo,
            agent_repo=self._agent_repo,
            shared_store=self._shared_store,
            message_repo=self._message_repo,
            event_log=self._event_log,
        )
        self._task_service = TaskService(
            task_repo=self._task_repo,
            instance_pool=self._instance_pool,
            role_registry=self._role_registry,
        )
        self._run_use_cases = RunUseCases(
            run_manager=self._run_manager,
            session_repo=self._session_repo,
        )
        self._session_use_cases = SessionUseCases(
            session_service=self._session_service,
        )
        self._task_use_cases = TaskUseCases(
            task_service=self._task_service,
        )

    def get_config_status(self) -> dict:
        return {
            "model": {
                "loaded": True,
                "profiles": list(self._runtime.llm_profiles.keys()),
            },
            "mcp": {
                "loaded": True,
                "servers": list(self._mcp_registry.list_names()),
            },
            "skills": {
                "loaded": True,
                "skills": list(self._skill_registry.list_names()),
            },
        }

    def get_model_config(self) -> dict:
        return self._config_manager.get_model_config()

    def get_model_profiles(self) -> dict:
        return self._config_manager.get_model_profiles()

    def save_model_profile(self, name: str, profile: dict) -> None:
        self._config_manager.save_model_profile(name, profile)
        self.reload_model_config()

    def delete_model_profile(self, name: str) -> None:
        self._config_manager.delete_model_profile(name)
        self.reload_model_config()

    def save_model_config(self, config: dict) -> None:
        self._config_manager.save_model_config(config)
        self.reload_model_config()

    def reload_model_config(self) -> None:
        self._runtime = load_runtime_config(
            config_dir=self._config_dir,
            roles_dir=self._roles_dir,
            db_path=self._db_path,
        )
        self._recreate_task_execution_service()

    def _recreate_task_execution_service(self) -> None:
        def get_task_execution_service():
            return self._task_execution_service

        self._provider_factory = create_provider_factory(
            runtime=self._runtime,
            task_repo=self._task_repo,
            instance_pool=self._instance_pool,
            shared_store=self._shared_store,
            event_log=self._event_log,
            injection_manager=self._injection_manager,
            run_event_hub=self._run_event_hub,
            agent_repo=self._agent_repo,
            tool_registry=self._tool_registry,
            mcp_registry=self._mcp_registry,
            skill_registry=self._skill_registry,
            message_repo=self._message_repo,
            role_registry=self._role_registry,
            run_control_manager=self._run_control_manager,
            tool_approval_manager=self._tool_approval_manager,
            tool_approval_policy=self._tool_approval_policy,
            get_task_execution_service=get_task_execution_service,
        )
        self._task_execution_service = create_task_execution_service(
            role_registry=self._role_registry,
            instance_pool=self._instance_pool,
            task_repo=self._task_repo,
            shared_store=self._shared_store,
            event_log=self._event_log,
            agent_repo=self._agent_repo,
            message_repo=self._message_repo,
            provider_factory=self._provider_factory,
            injection_manager=self._injection_manager,
            run_control_manager=self._run_control_manager,
        )

        self._meta_agent.coordinator.task_execution_service = (
            self._task_execution_service
        )

    def reload_mcp_config(self) -> None:
        self._mcp_registry = self._config_manager.load_mcp_registry()
        for role in self._role_registry.list_roles():
            self._mcp_registry.validate_known(role.mcp_servers)

    def reload_skills_config(self) -> None:
        self._skill_registry = self._config_manager.load_skill_registry()
        for role in self._role_registry.list_roles():
            self._skill_registry.validate_known(role.skills)

    async def run_intent(self, intent: IntentInput) -> RunResult:
        return await self._run_use_cases.run_intent(intent)

    def create_run(self, intent: IntentInput) -> tuple[str, str]:
        return self._run_use_cases.create_run(intent)

    def _ensure_run_started(self, run_id: str) -> None:
        self._run_use_cases.ensure_run_started(run_id)

    async def stream_run_events(self, run_id: str):
        async for event in self._run_use_cases.stream_run_events(run_id):
            yield event

    async def run_intent_stream(self, intent: IntentInput):
        async for event in self._run_use_cases.run_intent_stream(intent):
            yield event

    def inject_message(
        self, run_id: str, source: InjectionSource, content: str
    ) -> InjectionMessage:
        return self._run_use_cases.inject_message(run_id, source, content)

    def resolve_gate(
        self, run_id: str, task_id: str, action: str, feedback: str = ""
    ) -> None:
        self._run_use_cases.resolve_gate(run_id, task_id, action, feedback)

    def list_open_gates(self, run_id: str) -> list[dict]:
        return self._run_use_cases.list_open_gates(run_id)

    def resolve_tool_approval(
        self, run_id: str, tool_call_id: str, action: str, feedback: str = ''
    ) -> None:
        self._run_use_cases.resolve_tool_approval(run_id, tool_call_id, action, feedback)

    def list_open_tool_approvals(self, run_id: str) -> list[dict[str, str]]:
        return self._run_use_cases.list_open_tool_approvals(run_id)

    def dispatch_task_human(
        self, run_id: str, task_id: str, coordinator_instance_id: str
    ) -> None:
        self._run_use_cases.dispatch_task_human(run_id, task_id, coordinator_instance_id)

    def get_coordinator_instance_id(self, session_id: str) -> str | None:
        return self._run_use_cases.get_coordinator_instance_id(session_id)

    def dispatch_task_human_for_session(
        self, session_id: str, run_id: str, task_id: str
    ) -> None:
        self._run_use_cases.dispatch_task_human_for_session(session_id, run_id, task_id)

    def stop_run(self, run_id: str) -> None:
        self._run_use_cases.stop_run(run_id)

    def stop_subagent(self, run_id: str, instance_id: str) -> dict[str, str]:
        return self._run_use_cases.stop_subagent(run_id, instance_id)

    def inject_subagent_message(
        self,
        run_id: str,
        instance_id: str,
        content: str,
    ) -> None:
        self._run_use_cases.inject_subagent_message(run_id, instance_id, content)

    def create_workflow(self, spec: WorkflowSpec) -> str:
        self._workflows.append(spec)
        return spec.workflow_id

    def create_session(
        self, session_id: str | None = None, metadata: dict[str, str] | None = None
    ) -> SessionRecord:
        return self._session_use_cases.create_session(session_id=session_id, metadata=metadata)

    def update_session(self, session_id: str, metadata: dict[str, str]) -> None:
        self._session_use_cases.update_session(session_id, metadata)

    def delete_session(self, session_id: str) -> None:
        self._session_use_cases.delete_session(session_id)

    def get_session(self, session_id: str) -> SessionRecord:
        return self._session_use_cases.get_session(session_id)

    def list_sessions(self) -> tuple[SessionRecord, ...]:
        return self._session_use_cases.list_sessions()

    def submit_task(self, task: TaskEnvelope) -> str:
        return self._task_use_cases.submit_task(task)

    def query_task(self, task_id: str) -> TaskRecord:
        return self._task_use_cases.query_task(task_id)

    def list_tasks(self) -> tuple[TaskRecord, ...]:
        return self._task_use_cases.list_tasks()

    def create_subagent(self, role_id: str) -> SubAgentInstance:
        return self._task_use_cases.create_subagent(role_id)

    def list_roles(self) -> tuple[RoleDefinition, ...]:
        return self._task_use_cases.list_roles()

    def list_agents_in_session(self, session_id: str) -> tuple[AgentRuntimeRecord, ...]:
        return self._session_use_cases.list_agents_in_session(session_id)

    def get_agent_messages(self, session_id: str, instance_id: str) -> list[dict]:
        return self._session_use_cases.get_agent_messages(session_id, instance_id)

    def get_global_events(self, session_id: str) -> list[dict]:
        return self._session_use_cases.get_global_events(session_id)

    def get_session_messages(self, session_id: str) -> list[dict]:
        return self._session_use_cases.get_session_messages(session_id)

    def get_session_workflows(self, session_id: str) -> list[dict]:
        return self._session_use_cases.get_session_workflows(session_id)

    @staticmethod
    def _collect_pending_tool_approvals(
        parsed_events: list[tuple[dict, dict[str, Any]]],
    ) -> dict[str, list[dict[str, str]]]:
        return collect_pending_tool_approvals(parsed_events)

    @staticmethod
    def _collect_pending_stream_snapshots(
        parsed_events: list[tuple[dict, dict[str, Any]]],
        session_messages: list[dict[str, Any]],
        by_run_instance_role: dict[str, dict[str, str]],
    ) -> dict[str, dict[str, Any]]:
        return collect_pending_stream_snapshots(
            parsed_events,
            session_messages,
            by_run_instance_role,
        )

    def _build_session_rounds(self, session_id: str) -> list[dict]:
        return self._session_use_cases.build_session_rounds(session_id)

    def get_session_rounds(
        self,
        session_id: str,
        *,
        limit: int = 8,
        cursor_run_id: str | None = None,
    ) -> dict[str, object]:
        return self._session_use_cases.get_session_rounds(
            session_id,
            limit=limit,
            cursor_run_id=cursor_run_id,
        )

    def get_round(self, session_id: str, run_id: str) -> dict:
        return self._session_use_cases.get_round(session_id, run_id)

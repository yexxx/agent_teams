from __future__ import annotations

from agent_teams.core.models import RoleDefinition, SubAgentInstance, TaskEnvelope, TaskRecord


class TaskService:
    def __init__(
        self,
        *,
        task_repo,
        instance_pool,
        role_registry,
    ) -> None:
        self._task_repo = task_repo
        self._instance_pool = instance_pool
        self._role_registry = role_registry

    def submit_task(self, task: TaskEnvelope) -> str:
        self._task_repo.create(task)
        return task.task_id

    def query_task(self, task_id: str) -> TaskRecord:
        return self._task_repo.get(task_id)

    def list_tasks(self) -> tuple[TaskRecord, ...]:
        return self._task_repo.list_all()

    def create_subagent(self, role_id: str) -> SubAgentInstance:
        return self._instance_pool.create_subagent(role_id)

    def list_roles(self) -> tuple[RoleDefinition, ...]:
        return self._role_registry.list_roles()

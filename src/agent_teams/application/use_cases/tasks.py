from __future__ import annotations

from dataclasses import dataclass

from agent_teams.application.task_service import TaskService
from agent_teams.core.models import RoleDefinition, SubAgentInstance, TaskEnvelope, TaskRecord


@dataclass(slots=True)
class TaskUseCases:
    task_service: TaskService

    def submit_task(self, task: TaskEnvelope) -> str:
        return self.task_service.submit_task(task)

    def query_task(self, task_id: str) -> TaskRecord:
        return self.task_service.query_task(task_id)

    def list_tasks(self) -> tuple[TaskRecord, ...]:
        return self.task_service.list_tasks()

    def create_subagent(self, role_id: str) -> SubAgentInstance:
        return self.task_service.create_subagent(role_id)

    def list_roles(self) -> tuple[RoleDefinition, ...]:
        return self.task_service.list_roles()

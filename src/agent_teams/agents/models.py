# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agent_teams.agents.enums import InstanceStatus
from agent_teams.workspace.ids import build_conversation_id, build_workspace_id


class SubAgentInstance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instance_id: str = Field(min_length=1)
    role_id: str = Field(min_length=1)
    workspace_id: str = Field(min_length=1)
    conversation_id: str = Field(min_length=1)
    status: InstanceStatus = InstanceStatus.IDLE
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    last_active_at: datetime = Field(
        default_factory=lambda: datetime.now(tz=timezone.utc)
    )
    completed_tasks: int = 0
    failed_tasks: int = 0

    @model_validator(mode="before")
    @classmethod
    def _populate_workspace_defaults(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data

        payload = dict(data)
        role_id = payload.get("role_id")
        session_id = payload.get("session_id")
        workspace_id = payload.get("workspace_id")
        conversation_id = payload.get("conversation_id")
        if isinstance(session_id, str) and session_id and not workspace_id:
            payload["workspace_id"] = build_workspace_id(session_id)
        if (
            isinstance(session_id, str)
            and session_id
            and isinstance(role_id, str)
            and role_id
            and not conversation_id
        ):
            payload["conversation_id"] = build_conversation_id(session_id, role_id)
        return payload


class AgentRuntimeRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    instance_id: str = Field(min_length=1)
    role_id: str = Field(min_length=1)
    workspace_id: str = Field(min_length=1)
    conversation_id: str = Field(min_length=1)
    status: InstanceStatus
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))

    @model_validator(mode="before")
    @classmethod
    def _populate_workspace_defaults(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data

        payload = dict(data)
        session_id = payload.get("session_id")
        role_id = payload.get("role_id")
        workspace_id = payload.get("workspace_id")
        conversation_id = payload.get("conversation_id")
        if isinstance(session_id, str) and session_id and not workspace_id:
            payload["workspace_id"] = build_workspace_id(session_id)
        if (
            isinstance(session_id, str)
            and session_id
            and isinstance(role_id, str)
            and role_id
            and not conversation_id
        ):
            payload["conversation_id"] = build_conversation_id(session_id, role_id)
        return payload

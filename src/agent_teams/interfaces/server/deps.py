from __future__ import annotations

from fastapi import Request

from agent_teams.application.service import AgentTeamsService


def get_service(request: Request) -> AgentTeamsService:
    return request.app.state.service

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from agent_teams.application.service import AgentTeamsService
from agent_teams.core.enums import ExecutionMode, InjectionSource
from agent_teams.core.models import IntentInput
from agent_teams.interfaces.server.deps import get_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/runs", tags=["Runs"])


class CreateRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: str = Field(min_length=1)
    session_id: str | None = None
    execution_mode: ExecutionMode = ExecutionMode.AI
    confirmation_gate: bool = False


class CreateRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    session_id: str


class InjectMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: InjectionSource = InjectionSource.USER
    content: str = Field(min_length=1)


class ResolveGateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str
    feedback: str = ""


class DispatchTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)


@router.post("", response_model=CreateRunResponse)
def create_run(
    req: CreateRunRequest,
    service: AgentTeamsService = Depends(get_service),
) -> CreateRunResponse:
    run_id, session_id = service.create_run(
        IntentInput(
            session_id=req.session_id,
            intent=req.intent,
            execution_mode=req.execution_mode,
            confirmation_gate=req.confirmation_gate,
        )
    )
    return CreateRunResponse(run_id=run_id, session_id=session_id)


@router.get("/{run_id}/events")
async def stream_run_events(
    run_id: str,
    service: AgentTeamsService = Depends(get_service),
) -> StreamingResponse:
    async def event_generator():
        try:
            async for event in service.stream_run_events(run_id):
                yield f"data: {event.model_dump_json()}\n\n"
        except KeyError as exc:
            logger.exception("Run not found during stream start")
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
        except Exception as exc:  # pragma: no cover - defensive path
            logger.exception("Unexpected stream failure")
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/{run_id}/inject")
def inject_message(
    run_id: str,
    req: InjectMessageRequest,
    service: AgentTeamsService = Depends(get_service),
) -> dict:
    try:
        result = service.inject_message(run_id=run_id, source=req.source, content=req.content)
        return result.model_dump()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{run_id}/gates")
def list_open_gates(
    run_id: str,
    service: AgentTeamsService = Depends(get_service),
) -> list[dict]:
    return service.list_open_gates(run_id)


@router.post("/{run_id}/gates/{task_id}/resolve")
def resolve_gate(
    run_id: str,
    task_id: str,
    req: ResolveGateRequest,
    service: AgentTeamsService = Depends(get_service),
) -> dict[str, str]:
    try:
        service.resolve_gate(run_id=run_id, task_id=task_id, action=req.action, feedback=req.feedback)
        return {"status": "ok", "action": req.action}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{run_id}/dispatch")
def dispatch_task(
    run_id: str,
    req: DispatchTaskRequest,
    service: AgentTeamsService = Depends(get_service),
) -> dict[str, str]:
    try:
        service.dispatch_task_human_for_session(
            session_id=req.session_id,
            run_id=run_id,
            task_id=req.task_id,
        )
        return {"status": "ok", "dispatched_task_id": req.task_id}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

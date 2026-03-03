from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from agent_teams.application.service import AgentTeamsService
from agent_teams.interfaces.server.routers import roles, runs, sessions, system, tasks


def _get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent.parent.parent


DEFAULT_CONFIG_DIR = _get_project_root() / ".agent_teams"
FRONTEND_DIST_DIR = _get_project_root() / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.service = AgentTeamsService(config_dir=DEFAULT_CONFIG_DIR, debug=False)
    yield


app = FastAPI(
    title="Agent Teams Server",
    description="REST API for Agent Teams orchestration.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(system.router, prefix="/api")
app.include_router(sessions.router, prefix="/api")
app.include_router(runs.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")
app.include_router(roles.router, prefix="/api")

if FRONTEND_DIST_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST_DIR), html=True), name="frontend")
else:

    @app.get("/")
    def missing_frontend() -> JSONResponse:
        return JSONResponse(
            {
                "status": "frontend_not_built",
                "message": "Frontend build artifacts were not found in ./frontend/dist",
            }
        )

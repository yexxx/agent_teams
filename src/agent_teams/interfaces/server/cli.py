# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Callable
from importlib import import_module
from typing import cast

import typer


def serve(
    host: str = typer.Option("127.0.0.1", "--host", help="Host to bind the server to"),
    port: int = typer.Option(8000, "--port", help="Port to bind the server to"),
) -> None:
    uvicorn_module = import_module("uvicorn")
    server_module = import_module("agent_teams.interfaces.server.app")
    fastapi_app = getattr(server_module, "app")
    uvicorn_run = cast(Callable[..., None], getattr(uvicorn_module, "run"))

    typer.echo(f"Starting Agent Teams server on http://{host}:{port}")
    uvicorn_run(fastapi_app, host=host, port=port)


def build_server_app() -> typer.Typer:
    server_app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)
    server_app.command("serve")(serve)
    return server_app

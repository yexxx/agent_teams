# -*- coding: utf-8 -*-
from __future__ import annotations

from types import ModuleType
import sys

from agent_teams.interfaces.server import cli as server_cli


def test_serve_runs_uvicorn(monkeypatch) -> None:
    captured: dict[str, object] = {}

    fake_uvicorn = ModuleType("uvicorn")

    def fake_run(app: object, host: str, port: int) -> None:
        captured["app"] = app
        captured["host"] = host
        captured["port"] = port

    setattr(fake_uvicorn, "run", fake_run)

    fake_server_module = ModuleType("agent_teams.interfaces.server.app")
    sentinel_app = object()
    setattr(fake_server_module, "app", sentinel_app)

    monkeypatch.setitem(sys.modules, "uvicorn", fake_uvicorn)
    monkeypatch.setitem(
        sys.modules, "agent_teams.interfaces.server.app", fake_server_module
    )

    server_cli.serve(host="127.0.0.1", port=8911)

    assert captured == {
        "app": sentinel_app,
        "host": "127.0.0.1",
        "port": 8911,
    }

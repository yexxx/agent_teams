# -*- coding: utf-8 -*-
from __future__ import annotations

from typer.testing import CliRunner

from agent_teams.interfaces.cli import app as cli_app

runner = CliRunner()


def test_triggers_create_builds_expected_payload(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_autostart(base_url: str, autostart: bool) -> None:
        captured["base_url"] = base_url
        captured["autostart"] = autostart

    def fake_request_json(
        base_url: str,
        method: str,
        path: str,
        payload: dict[str, object] | None = None,
        extra_headers: dict[str, str] | None = None,
        timeout_seconds: float = 30.0,
    ) -> dict[str, object] | list[object]:
        _ = (base_url, timeout_seconds)
        captured["method"] = method
        captured["path"] = path
        captured["payload"] = payload
        captured["extra_headers"] = extra_headers
        return {"trigger_id": "trg_1", "name": "repo_push"}

    monkeypatch.setattr(cli_app, "_auto_start_if_needed", fake_autostart)
    monkeypatch.setattr(cli_app, "_request_json", fake_request_json)

    result = runner.invoke(
        cli_app.app,
        [
            "triggers",
            "create",
            "--name",
            "repo_push",
            "--source-type",
            "webhook",
            "--display-name",
            "Repo Push",
            "--source-config-json",
            '{"provider":"github"}',
            "--auth-policies-json",
            '[{"mode":"none"}]',
            "--target-config-json",
            '{"kind":"noop"}',
            "--public-token",
            "tok_123",
        ],
    )

    assert result.exit_code == 0
    assert captured == {
        "base_url": cli_app.DEFAULT_BASE_URL,
        "autostart": True,
        "method": "POST",
        "path": "/api/triggers",
        "payload": {
            "name": "repo_push",
            "source_type": "webhook",
            "source_config": {"provider": "github"},
            "auth_policies": [{"mode": "none"}],
            "target_config": {"kind": "noop"},
            "public_token": "tok_123",
            "display_name": "Repo Push",
            "enabled": True,
        },
        "extra_headers": None,
    }


def test_triggers_webhook_parses_headers(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_autostart(base_url: str, autostart: bool) -> None:
        _ = (base_url, autostart)

    def fake_request_json(
        base_url: str,
        method: str,
        path: str,
        payload: dict[str, object] | None = None,
        extra_headers: dict[str, str] | None = None,
        timeout_seconds: float = 30.0,
    ) -> dict[str, object] | list[object]:
        _ = (base_url, timeout_seconds)
        captured["method"] = method
        captured["path"] = path
        captured["payload"] = payload
        captured["extra_headers"] = extra_headers
        return {"accepted": True}

    monkeypatch.setattr(cli_app, "_auto_start_if_needed", fake_autostart)
    monkeypatch.setattr(cli_app, "_request_json", fake_request_json)

    result = runner.invoke(
        cli_app.app,
        [
            "triggers",
            "webhook",
            "--public-token",
            "tok_123",
            "--body-json",
            '{"payload":{"action":"push"}}',
            "-H",
            "X-Token:abc",
            "-H",
            "X-Event:push",
        ],
    )

    assert result.exit_code == 0
    assert captured == {
        "method": "POST",
        "path": "/api/triggers/webhooks/tok_123",
        "payload": {"payload": {"action": "push"}},
        "extra_headers": {"X-Token": "abc", "X-Event": "push"},
    }

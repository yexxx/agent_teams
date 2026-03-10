# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path

from agent_teams.providers.model_config import DEFAULT_LLM_CONNECT_TIMEOUT_SECONDS
from agent_teams.providers.model_config_manager import ModelConfigManager


def test_get_model_config_returns_empty_when_file_missing(tmp_path: Path) -> None:
    manager = ModelConfigManager(config_dir=tmp_path)

    assert manager.get_model_config() == {}


def test_save_model_profile_and_get_model_profiles(tmp_path: Path) -> None:
    manager = ModelConfigManager(config_dir=tmp_path)

    manager.save_model_profile(
        "default",
        {
            "provider": "openai_compatible",
            "model": "gpt-4o-mini",
            "base_url": "https://example.test/v1",
            "api_key": "secret-key",
            "temperature": 0.25,
            "top_p": 0.9,
            "max_tokens": 2000,
            "connect_timeout_seconds": 45.0,
        },
    )

    profiles = manager.get_model_profiles()

    assert profiles["default"]["provider"] == "openai_compatible"
    assert profiles["default"]["has_api_key"] is True
    assert profiles["default"]["temperature"] == 0.25
    assert profiles["default"]["max_tokens"] == 2000
    assert profiles["default"]["connect_timeout_seconds"] == 45.0


def test_get_model_profiles_uses_default_connect_timeout_when_missing(
    tmp_path: Path,
) -> None:
    manager = ModelConfigManager(config_dir=tmp_path)
    model_file = tmp_path / "model.json"
    model_file.write_text(
        json.dumps(
            {
                "default": {
                    "provider": "openai_compatible",
                    "model": "gpt-4o-mini",
                    "base_url": "https://example.test/v1",
                    "api_key": "secret-key",
                }
            }
        ),
        encoding="utf-8",
    )

    profiles = manager.get_model_profiles()

    assert (
        profiles["default"]["connect_timeout_seconds"]
        == DEFAULT_LLM_CONNECT_TIMEOUT_SECONDS
    )


def test_delete_model_profile_removes_entry(tmp_path: Path) -> None:
    manager = ModelConfigManager(config_dir=tmp_path)
    model_file = tmp_path / "model.json"
    model_file.write_text(
        json.dumps(
            {
                "default": {
                    "provider": "openai_compatible",
                    "model": "gpt-4o-mini",
                    "base_url": "https://example.test/v1",
                    "api_key": "secret-key",
                },
                "secondary": {
                    "provider": "echo",
                    "model": "echo",
                    "base_url": "http://localhost",
                    "api_key": "none",
                },
            }
        ),
        encoding="utf-8",
    )

    manager.delete_model_profile("default")
    config = manager.get_model_config()

    assert "default" not in config
    assert "secondary" in config

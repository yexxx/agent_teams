# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from agent_teams.env import runtime_env


def test_load_merged_env_vars_project_overrides_user(tmp_path: Path) -> None:
    user_home = tmp_path / "home"
    project_root = tmp_path / "repo"

    user_env_dir = user_home / ".agent_teams"
    project_env_dir = project_root / ".agent_teams"
    user_env_dir.mkdir(parents=True)
    project_env_dir.mkdir(parents=True)

    (user_env_dir / ".env").write_text(
        "SHARED_KEY=user\nUSER_ONLY=one\n",
        encoding="utf-8",
    )
    (project_env_dir / ".env").write_text(
        "SHARED_KEY=project\nPROJECT_ONLY=two\n",
        encoding="utf-8",
    )

    merged = runtime_env.load_merged_env_vars(
        project_root=project_root,
        user_home_dir=user_home,
        include_process_env=False,
    )

    assert merged["SHARED_KEY"] == "project"
    assert merged["USER_ONLY"] == "one"
    assert merged["PROJECT_ONLY"] == "two"


def test_get_env_var_process_env_has_highest_priority(
    tmp_path: Path,
    monkeypatch,
) -> None:
    user_home = tmp_path / "home"
    project_root = tmp_path / "repo"

    user_env_dir = user_home / ".agent_teams"
    project_env_dir = project_root / ".agent_teams"
    user_env_dir.mkdir(parents=True)
    project_env_dir.mkdir(parents=True)

    (user_env_dir / ".env").write_text("ENV_KEY=user\n", encoding="utf-8")
    (project_env_dir / ".env").write_text("ENV_KEY=project\n", encoding="utf-8")
    monkeypatch.setenv("ENV_KEY", "process")

    value = runtime_env.get_env_var(
        "ENV_KEY",
        project_root=project_root,
        user_home_dir=user_home,
    )

    assert value == "process"


def test_load_env_file_ignores_invalid_lines_and_strips_quotes(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# comment\nINVALID_LINE\nA=1\nB='two'\nC=\"three\"\n",
        encoding="utf-8",
    )

    values = runtime_env.load_env_file(env_file)

    assert values == {"A": "1", "B": "two", "C": "three"}


def test_get_env_var_returns_default_when_missing(tmp_path: Path) -> None:
    user_home = tmp_path / "home"
    project_root = tmp_path / "repo"

    value = runtime_env.get_env_var(
        "MISSING_KEY",
        default="fallback",
        project_root=project_root,
        user_home_dir=user_home,
        include_process_env=False,
    )

    assert value == "fallback"


def test_get_project_env_file_path_falls_back_to_cwd_when_git_root_is_missing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    config_dir = tmp_path.resolve() / ".agent_teams"
    monkeypatch.setattr(
        runtime_env, "get_project_config_dir", lambda **kwargs: config_dir
    )

    env_file_path = runtime_env.get_project_env_file_path()

    assert env_file_path == config_dir / ".env"

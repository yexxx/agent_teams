# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from agent_teams.interfaces.server import config_paths


def test_get_frontend_dist_dir_uses_git_root_when_available(monkeypatch) -> None:
    project_root = Path("D:/repo-root").resolve()
    monkeypatch.setattr(config_paths, "get_project_root_or_none", lambda: project_root)

    frontend_dist_dir = config_paths.get_frontend_dist_dir()

    assert frontend_dist_dir == project_root / "frontend" / "dist"


def test_get_frontend_dist_dir_falls_back_to_cwd_when_git_root_is_missing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(config_paths, "get_project_root_or_none", lambda: None)

    frontend_dist_dir = config_paths.get_frontend_dist_dir()

    assert frontend_dist_dir == tmp_path.resolve() / "frontend" / "dist"

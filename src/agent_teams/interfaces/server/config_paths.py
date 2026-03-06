# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from agent_teams.paths import get_project_root_or_none


def get_frontend_dist_dir() -> Path:
    project_root = get_project_root_or_none() or Path.cwd().resolve()
    return project_root / "frontend" / "dist"

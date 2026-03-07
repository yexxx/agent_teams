# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import pytest

from agent_teams.state.scope_models import ScopeRef, ScopeType, StateMutation
from agent_teams.state.shared_state_repo import SharedStateRepository
from agent_teams.workspace import (
    StateScope,
    WorkspaceFileScope,
    WorkspaceManager,
    WorkspaceProfile,
    default_workspace_profile,
)


def test_workspace_memory_snapshot_follows_role_scopes(tmp_path: Path) -> None:
    db_path = tmp_path / "workspace_memory.db"
    shared_store = SharedStateRepository(db_path)
    manager = WorkspaceManager(project_root=tmp_path, shared_store=shared_store)
    workspace = manager.resolve(
        session_id="session-1",
        role_id="time",
        instance_id="inst-1",
        profile=default_workspace_profile(),
    )

    shared_store.manage_state(
        StateMutation(
            scope=ScopeRef(
                scope_type=ScopeType.WORKSPACE,
                scope_id=workspace.ref.workspace_id,
            ),
            key="project",
            value_json='"workspace"',
        )
    )
    shared_store.manage_state(
        StateMutation(
            scope=ScopeRef(
                scope_type=ScopeType.ROLE,
                scope_id=f"{workspace.ref.session_id}:{workspace.ref.role_id}",
            ),
            key="preference",
            value_json='"role"',
        )
    )
    workspace.memory.write_conversation_memory(
        key="recent",
        value_json='"conversation"',
    )

    snapshot = dict(workspace.memory.prompt_snapshot())

    assert snapshot["project"] == '"workspace"'
    assert snapshot["preference"] == '"role"'
    assert snapshot["recent"] == '"conversation"'


def test_workspace_memory_rejects_writes_outside_profile(tmp_path: Path) -> None:
    db_path = tmp_path / "workspace_profile.db"
    manager = WorkspaceManager(
        project_root=tmp_path,
        shared_store=SharedStateRepository(db_path),
    )
    workspace = manager.resolve(
        session_id="session-1",
        role_id="time",
        instance_id="inst-1",
        profile=WorkspaceProfile(
            binding=default_workspace_profile().binding,
            backend=default_workspace_profile().backend,
            capabilities=default_workspace_profile().capabilities,
            readable_scopes=(StateScope.ROLE,),
            writable_scopes=(StateScope.ROLE,),
            persistent_scopes=(StateScope.ROLE,),
        ),
    )

    with pytest.raises(ValueError, match="not writable"):
        workspace.memory.write_conversation_memory(
            key="recent",
            value_json='"conversation"',
        )


def test_workspace_file_scope_enforces_read_and_write_roots(tmp_path: Path) -> None:
    db_path = tmp_path / "workspace_scope.db"
    project_root = tmp_path / "project"
    project_root.mkdir()
    shared_store = SharedStateRepository(db_path)
    manager = WorkspaceManager(project_root=project_root, shared_store=shared_store)
    workspace = manager.resolve(
        session_id="session-1",
        role_id="spec_coder",
        instance_id="inst-1",
        profile=WorkspaceProfile(
            binding=default_workspace_profile().binding,
            backend=default_workspace_profile().backend,
            capabilities=default_workspace_profile().capabilities,
            readable_scopes=default_workspace_profile().readable_scopes,
            writable_scopes=default_workspace_profile().writable_scopes,
            persistent_scopes=default_workspace_profile().persistent_scopes,
            file_scope=WorkspaceFileScope(
                working_directory=".",
                readable_paths=("src", "docs"),
                writable_paths=("src",),
            ),
        ),
    )

    assert (
        workspace.resolve_path("src/app.py", write=False)
        == (project_root / "src" / "app.py").resolve()
    )
    assert (
        workspace.resolve_path("src/app.py", write=True)
        == (project_root / "src" / "app.py").resolve()
    )

    with pytest.raises(ValueError, match="outside workspace write scope"):
        workspace.resolve_path("docs/spec.md", write=True)

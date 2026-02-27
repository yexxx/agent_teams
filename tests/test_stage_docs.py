import pytest
from pathlib import Path
from uuid import uuid4

from agent_teams.tools.stage_docs import current_stage_doc_path, previous_stage_doc_path
from agent_teams.tools.stage_docs import write_stage_doc_once


def test_stage_doc_paths() -> None:
    root = Path('D:/workspace/agent_teams')
    run_id = 'run123'

    assert str(current_stage_doc_path(workspace_root=root, run_id=run_id, role_id='spec_builder')).endswith(
        '.agent_teams/stage_docs/run123/spec.md'.replace('/', '\\')
    )
    assert str(current_stage_doc_path(workspace_root=root, run_id=run_id, role_id='design_builder')).endswith(
        '.agent_teams/stage_docs/run123/design.md'.replace('/', '\\')
    )
    assert str(current_stage_doc_path(workspace_root=root, run_id=run_id, role_id='verify')).endswith(
        '.agent_teams/stage_docs/run123/verify.md'.replace('/', '\\')
    )

    assert str(previous_stage_doc_path(workspace_root=root, run_id=run_id, role_id='design_builder')).endswith(
        '.agent_teams/stage_docs/run123/spec.md'.replace('/', '\\')
    )
    assert str(previous_stage_doc_path(workspace_root=root, run_id=run_id, role_id='verify')).endswith(
        '.agent_teams/stage_docs/run123/design.md'.replace('/', '\\')
    )


def test_write_stage_doc_once_rejects_duplicate() -> None:
    path = Path(f'.agent_teams/smoke_stage_doc_once_{uuid4().hex}.md')
    write_stage_doc_once(path=path, content='v1')
    with pytest.raises(ValueError):
        write_stage_doc_once(path=path, content='v2')
